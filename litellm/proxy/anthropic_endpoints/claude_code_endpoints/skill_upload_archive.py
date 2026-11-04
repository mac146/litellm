import hashlib
import io
import json
import re
import struct
import zipfile
from dataclasses import dataclass
from typing import Final

from litellm.proxy.discovery_endpoints.agent_skills_archive import build_skill_archive

MAX_SKILL_UPLOAD_BYTES: Final = 10 * 1024 * 1024
MAX_SKILL_ARCHIVE_COMPRESSION_RATIO: Final = 50


@dataclass(frozen=True, slots=True)
class UploadedSkillArchive:
    content: bytes
    digest: str


def build_uploaded_skill_archive(content: bytes, name: str) -> UploadedSkillArchive | None:
    if len(content) > MAX_SKILL_UPLOAD_BYTES or re.fullmatch(r"[a-z0-9-]+", name) is None:
        return None
    try:
        return _build_uploaded_skill_archive(content, name)
    except (struct.error, UnicodeEncodeError):
        return None


def _build_uploaded_skill_archive(content: bytes, name: str) -> UploadedSkillArchive | None:
    skill: Final = build_skill_archive(content, ignore_macos_metadata=True, read_frontmatter=False)
    if skill is None:
        return None

    manifest: Final = {"name": name}
    with zipfile.ZipFile(io.BytesIO(skill.content)) as files:
        members: Final = ((".claude-plugin/plugin.json", json.dumps(manifest).encode()),) + tuple(
            (f"skills/{name}/{entry.filename}", files.read(entry)) for entry in files.infolist()
        )
    compressed: Final = _pack(members, zipfile.ZIP_DEFLATED)
    result: Final = (
        _pack(members, zipfile.ZIP_STORED)
        if sum(len(data) for _, data in members) > len(compressed) * MAX_SKILL_ARCHIVE_COMPRESSION_RATIO
        else compressed
    )
    return UploadedSkillArchive(content=result, digest=hashlib.sha256(result).hexdigest())


def _pack(members: tuple[tuple[str, bytes], ...], compression: int) -> bytes:
    buffer: Final = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as plugin:
        for name, data in members:
            plugin.writestr(zipfile.ZipInfo(name), data, compress_type=compression)
    return buffer.getvalue()
