from pathlib import Path
from zipfile import ZipFile

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    ExportWorldRequest,
    ImportWorldRequest,
    ResetWorldRequest,
)
from bedrock_server_manager.api.world import export_world, import_world, reset_world
from bedrock_server_manager.error import BSMError


async def test_world_api_exports_imports_and_resets_actual_world(
    app_context, populated_server, tmp_path
):
    server = populated_server
    world = Path(server.server_dir) / "worlds" / await server.get_world_name()
    marker = world / "integration.txt"
    marker.write_text("saved world")
    exported = await export_world(
        ExportWorldRequest(
            server_name=server.server_name, export_dir=str(tmp_path / "exports")
        ),
        app_context=app_context,
    )
    with ZipFile(exported.export_file) as archive:
        assert archive.read("integration.txt") == b"saved world"
    marker.write_text("changed world")
    response = await import_world(
        ImportWorldRequest(
            server_name=server.server_name, selected_file_path=exported.export_file
        ),
        app_context=app_context,
    )
    assert response.status == "success"
    assert marker.read_text() == "saved world"
    assert (
        await reset_world(
            ResetWorldRequest(server_name=server.server_name), app_context=app_context
        )
    ).status == "success"
    assert not world.exists()


async def test_invalid_world_import_preserves_live_content(
    app_context, populated_server, tmp_path
):
    server = populated_server
    world = Path(server.server_dir) / "worlds" / await server.get_world_name()
    original = (world / "level.dat").read_bytes()
    broken = tmp_path / "broken.mcworld"
    broken.write_bytes(b"not an archive")
    with pytest.raises(BSMError):
        await import_world(
            ImportWorldRequest(
                server_name=server.server_name, selected_file_path=str(broken)
            ),
            app_context=app_context,
        )
    assert (world / "level.dat").read_bytes() == original


@pytest.mark.parametrize(
    "model,payload",
    [
        (ExportWorldRequest, {"server_name": ""}),
        (ImportWorldRequest, {"server_name": "test_server", "selected_file_path": ""}),
        (ResetWorldRequest, {"server_name": ""}),
    ],
)
def test_world_request_rejects_missing_inputs(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)
