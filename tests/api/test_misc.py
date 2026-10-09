import os

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.misc import prune_download_cache
from bedrock_server_manager.api.models import PruneDownloadCacheRequest


@pytest.mark.parametrize("explicit", [True, False])
async def test_download_retention_removes_only_old_server_archives(
    app_context, tmp_path, explicit
):
    for index in range(4):
        archive = tmp_path / f"bedrock-server-1.0.{index}.zip"
        archive.write_bytes(b"archive")
        os.utime(archive, (100 + index, 100 + index))
    unrelated = tmp_path / "custom.zip"
    unrelated.write_bytes(b"custom")
    await app_context.settings.set("retention.downloads", 2)
    request = PruneDownloadCacheRequest(
        download_dir=str(tmp_path), **({"keep_count": 2} if explicit else {})
    )
    response = await prune_download_cache(request, app_context=app_context)
    assert response.status == "success"
    assert {path.name for path in tmp_path.iterdir() if path.is_file()} == {
        "bedrock-server-1.0.2.zip",
        "bedrock-server-1.0.3.zip",
        "custom.zip",
    }


def test_download_retention_rejects_negative_count():
    with pytest.raises(ValidationError):
        PruneDownloadCacheRequest(download_dir="downloads", keep_count=-1)
