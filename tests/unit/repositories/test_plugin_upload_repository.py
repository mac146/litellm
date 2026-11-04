import json
from typing import Final
from unittest.mock import AsyncMock, MagicMock

import pytest
from prisma import Base64, models

from litellm.models.plugin_upload import PluginArchiveMetadata
from litellm.repositories.plugin_upload_repository import PluginUploadRepository


@pytest.mark.asyncio
async def test_metadata_reads_writer_without_loading_archive() -> None:
    source: Final = {"source": "url", "url": "https://gateway.example/archive.zip"}
    manifest_json: Final = json.dumps({"name": "personal-skill", "source": source})
    prisma: Final = MagicMock()
    plugins: Final = prisma.writer_db.litellm_claudecodeplugintable
    plugins.find_unique = AsyncMock(
        return_value=models.LiteLLM_ClaudeCodePluginTable(
            id="plugin-id", name="personal-skill", enabled=False, manifest_json=manifest_json
        )
    )

    metadata: Final = await PluginUploadRepository(prisma).get_metadata("personal-skill")

    assert metadata == PluginArchiveMetadata("personal-skill", False, source, manifest_json)
    plugins.find_unique.assert_awaited_once_with(where={"name": "personal-skill"})
    assert prisma.writer_db.litellm_claudecodepluginupload.mock_calls == []
    assert prisma.db.mock_calls == []


@pytest.mark.asyncio
async def test_missing_metadata_does_not_load_archive() -> None:
    prisma: Final = MagicMock()
    prisma.writer_db.litellm_claudecodeplugintable.find_unique = AsyncMock(return_value=None)

    assert await PluginUploadRepository(prisma).get_metadata("missing-skill") is None
    assert prisma.writer_db.litellm_claudecodepluginupload.mock_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("manifest_json", [None, '{"source":{"source":"url","url":"https://gateway.example/a.zip"}}'])
async def test_content_read_is_fenced_by_authorized_metadata(enabled: bool, manifest_json: str | None) -> None:
    prisma: Final = MagicMock()
    archives: Final = prisma.writer_db.litellm_claudecodepluginupload
    content: Final = b"private archive bytes"
    archives.find_first = AsyncMock(
        return_value=models.LiteLLM_ClaudeCodePluginUpload(plugin_name="personal-skill", content=Base64.encode(content))
    )
    metadata: Final = PluginArchiveMetadata("personal-skill", enabled, {}, manifest_json)

    assert await PluginUploadRepository(prisma).get_content(metadata) == content
    archives.find_first.assert_awaited_once_with(
        where={
            "plugin_name": "personal-skill",
            "plugin": {"is": {"manifest_json": manifest_json, "enabled": enabled}},
        }
    )
    assert prisma.writer_db.litellm_claudecodeplugintable.mock_calls == []
    assert prisma.db.mock_calls == []


@pytest.mark.asyncio
async def test_content_missing_or_changed_after_authorization_returns_none() -> None:
    prisma: Final = MagicMock()
    prisma.writer_db.litellm_claudecodepluginupload.find_first = AsyncMock(return_value=None)

    assert (
        await PluginUploadRepository(prisma).get_content(PluginArchiveMetadata("personal-skill", True, {}, None))
        is None
    )
