import hashlib
import io
import json
import stat
import zipfile
from typing import Final

import pytest

from litellm.proxy.anthropic_endpoints.claude_code_endpoints.skill_upload_archive import (
    MAX_SKILL_ARCHIVE_COMPRESSION_RATIO,
    MAX_SKILL_UPLOAD_BYTES,
    build_uploaded_skill_archive,
)
from litellm.proxy.discovery_endpoints.agent_skills_archive import (
    MAX_ARCHIVE_ENTRIES,
    MAX_ARCHIVE_UNPACKED_BYTES,
)

MANIFEST: Final = b"---\nname: personal-skill\ndescription: Summarize notes\n---\nRead references/guide.md"


def _zip(files: tuple[tuple[str | zipfile.ZipInfo, bytes], ...], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer: Final = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        for name, content in files:
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.parametrize("prefix", ("", "personal-skill/"))
def test_upload_becomes_an_installable_plugin_with_supporting_files(prefix: str) -> None:
    upload: Final = _zip(
        (
            (f"{prefix}SKILL.md", MANIFEST),
            (f"{prefix}references/guide.md", b"Keep filenames unchanged"),
            (f"{prefix}scripts/read.py", b"print('notes')\n"),
            (f"{prefix}.DS_Store", b"Finder metadata"),
            ("__MACOSX/._SKILL.md", b"Finder resource fork"),
        )
    )
    result: Final = build_uploaded_skill_archive(upload, "registered-name")

    assert result is not None
    with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
        assert {name: archive.read(name) for name in archive.namelist()} == {
            ".claude-plugin/plugin.json": json.dumps({"name": "registered-name"}).encode(),
            "skills/registered-name/SKILL.md": MANIFEST,
            "skills/registered-name/references/guide.md": b"Keep filenames unchanged",
            "skills/registered-name/scripts/read.py": b"print('notes')\n",
        }
    assert result.digest == hashlib.sha256(result.content).hexdigest()
    assert build_uploaded_skill_archive(upload, "registered-name") == result


def test_upload_preserves_deep_skill_frontmatter_without_interpreting_yaml() -> None:
    manifest: Final = b"---\nnotes: " + b"[" * 1000 + b"0" + b"]" * 1000 + b"\n---\nRead references/guide.md"
    result: Final = build_uploaded_skill_archive(_zip((("SKILL.md", manifest),)), "skill")

    assert result is not None
    with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
        assert archive.read("skills/skill/SKILL.md") == manifest


@pytest.mark.parametrize("reference", (b"Read the guide", b"0,0,0,0,0,0,0,0,0,0\n" * 10000))
def test_upload_avoids_excessive_expansion_without_changing_files(reference: bytes) -> None:
    upload: Final = _zip((("SKILL.md", MANIFEST), ("reference.csv", reference)))
    result: Final = build_uploaded_skill_archive(upload, "skill")

    assert result is not None
    with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
        assert {entry.filename: archive.read(entry) for entry in archive.infolist()} == {
            ".claude-plugin/plugin.json": b'{"name": "skill"}',
            "skills/skill/SKILL.md": MANIFEST,
            "skills/skill/reference.csv": reference,
        }
        assert (
            sum(entry.file_size for entry in archive.infolist())
            <= len(result.content) * MAX_SKILL_ARCHIVE_COMPRESSION_RATIO
        )
        assert archive.getinfo("skills/skill/reference.csv").compress_type == (
            zipfile.ZIP_DEFLATED if reference == b"Read the guide" else zipfile.ZIP_STORED
        )
    assert result.digest == hashlib.sha256(result.content).hexdigest()
    assert build_uploaded_skill_archive(upload, "skill") == result


@pytest.mark.parametrize(
    "path",
    (
        "../escape",
        "/absolute",
        "C:/escape",
        "a\\escape",
        "__MACOSX/../escape",
        "bad/./file",
    ),
)
def test_unsafe_paths_are_rejected_even_in_ignored_metadata(path: str) -> None:
    upload: Final = _zip((("SKILL.md", MANIFEST), (path, b"unsafe")))
    assert build_uploaded_skill_archive(upload, "skill") is None


def test_duplicate_normalized_metadata_paths_are_rejected_before_filtering() -> None:
    upload: Final = _zip((("SKILL.md", MANIFEST), ("__MACOSX/a", b"first"), ("__MACOSX//a", b"second")))
    assert build_uploaded_skill_archive(upload, "skill") is None


def test_symlinks_are_rejected_even_in_ignored_metadata() -> None:
    link: Final = zipfile.ZipInfo("__MACOSX/link")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    upload: Final = _zip((("SKILL.md", MANIFEST), (link, b"../../outside")))
    assert build_uploaded_skill_archive(upload, "skill") is None


@pytest.mark.parametrize("name", ("../escape", "", "Not a slug"))
def test_registered_name_cannot_create_unsafe_plugin_paths(name: str) -> None:
    assert build_uploaded_skill_archive(_zip((("SKILL.md", MANIFEST),)), name) is None


def test_upload_rejects_registered_name_that_exceeds_zip_filename_limit() -> None:
    assert build_uploaded_skill_archive(_zip((("SKILL.md", MANIFEST),)), "x" * 65536) is None


@pytest.mark.parametrize(
    "files",
    (
        (("readme.md", b"no skill"),),
        (("wrapper/nested/SKILL.md", MANIFEST),),
        ((".claude-plugin/plugin.json", b'{"name":"plugin"}'), ("skills/example/SKILL.md", MANIFEST)),
    ),
)
def test_upload_requires_an_ordinary_skill_folder(files: tuple[tuple[str, bytes], ...]) -> None:
    assert build_uploaded_skill_archive(_zip(files), "skill") is None


def test_upload_size_limit_rejects_an_otherwise_valid_archive() -> None:
    upload: Final = _zip((("SKILL.md", MANIFEST), ("asset.bin", b"x" * MAX_SKILL_UPLOAD_BYTES)), zipfile.ZIP_STORED)
    assert build_uploaded_skill_archive(upload, "skill") is None


def test_expanded_size_limit_counts_ignored_metadata() -> None:
    upload: Final = _zip((("SKILL.md", MANIFEST), ("__MACOSX/large", b"x" * MAX_ARCHIVE_UNPACKED_BYTES)))
    assert build_uploaded_skill_archive(upload, "skill") is None


def test_entry_limit_counts_ignored_metadata() -> None:
    files: Final = (("SKILL.md", MANIFEST),) + tuple((f"__MACOSX/{index}", b"") for index in range(MAX_ARCHIVE_ENTRIES))
    assert build_uploaded_skill_archive(_zip(files), "skill") is None


def test_invalid_and_corrupt_zip_uploads_are_rejected() -> None:
    upload: Final = _zip((("SKILL.md", MANIFEST),), zipfile.ZIP_STORED)
    corrupt: Final = upload.replace(b"Summarize notes", b"Corrupted notes")
    assert build_uploaded_skill_archive(corrupt, "skill") is None
    assert build_uploaded_skill_archive(b"not a zip", "skill") is None


def test_encrypted_entries_are_rejected_even_in_ignored_metadata() -> None:
    upload: Final = _zip((("__MACOSX/encrypted", b"secret"), ("SKILL.md", MANIFEST)))
    central: Final = upload.index(b"PK\x01\x02")
    encrypted: Final = upload[: central + 8] + b"\x01\x00" + upload[central + 10 :]
    assert build_uploaded_skill_archive(encrypted, "skill") is None
