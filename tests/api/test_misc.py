import os

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.misc import prune_download_cache
from bedrock_server_manager.api.models import PruneDownloadCacheRequest


async def test_download_retention_and_validation(app_context, tmp_path):
    with pytest.raises(ValidationError):
        PruneDownloadCacheRequest(download_dir="downloads", keep_count=-1)

    await app_context.settings.set("retention.downloads", 2)
    for explicit in (True, False):
        target = tmp_path / f"dir_{explicit}"
        target.mkdir()
        for index in range(4):
            archive = target / f"bedrock-server-1.0.{index}.zip"
            archive.write_bytes(b"archive")
            os.utime(archive, (100 + index, 100 + index))
        unrelated = target / "custom.zip"
        unrelated.write_bytes(b"custom")
        request = PruneDownloadCacheRequest(
            download_dir=str(target), **({"keep_count": 2} if explicit else {})
        )
        response = await prune_download_cache(request, app_context=app_context)
        assert response.status == "success"
        assert {path.name for path in target.iterdir() if path.is_file()} == {
            "bedrock-server-1.0.2.zip",
            "bedrock-server-1.0.3.zip",
            "custom.zip",
        }
