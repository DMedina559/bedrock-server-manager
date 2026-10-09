from pathlib import Path

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.allowlist import (
    add_to_allowlist,
    get_allowlist,
    remove_from_allowlist,
)
from bedrock_server_manager.api.models import (
    AddToAllowlistRequest,
    GetAllowlistRequest,
    RemoveFromAllowlistRequest,
)
from bedrock_server_manager.error import BSMError


async def test_allowlist_api_persists_and_reports_missing_players(
    app_context, real_bedrock_server
):
    name = real_bedrock_server.server_name
    request = AddToAllowlistRequest(
        server_name=name, new_players_data=[{"name": "p1", "xuid": "123"}]
    )
    assert (await add_to_allowlist(request, app_context=app_context)).added_count == 1
    assert (await add_to_allowlist(request, app_context=app_context)).added_count == 0
    result = await get_allowlist(
        GetAllowlistRequest(server_name=name), app_context=app_context
    )
    assert any(p.name == "p1" and p.xuid == "123" for p in result.players)
    result = await remove_from_allowlist(
        RemoveFromAllowlistRequest(server_name=name, player_names=["p1", "p2"]),
        app_context=app_context,
    )
    assert result.details.removed == ["p1"]
    assert result.details.not_found == ["p2"]
    assert not any(
        p.name == "p1"
        for p in (
            await get_allowlist(
                GetAllowlistRequest(server_name=name), app_context=app_context
            )
        ).players
    )


@pytest.mark.parametrize(
    "model,payload",
    [
        (AddToAllowlistRequest, {"server_name": "", "new_players_data": []}),
        (
            AddToAllowlistRequest,
            {"server_name": "test_server", "new_players_data": "invalid"},
        ),
        (GetAllowlistRequest, {"server_name": ""}),
        (RemoveFromAllowlistRequest, {"server_name": "", "player_names": ["p1"]}),
    ],
)
def test_allowlist_requests_reject_invalid_input(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


async def test_allowlist_empty_removal_preserves_disk(app_context, real_bedrock_server):
    path = Path(real_bedrock_server.server_dir) / "allowlist.json"
    original = path.read_bytes()
    result = await remove_from_allowlist(
        RemoveFromAllowlistRequest(
            server_name=real_bedrock_server.server_name, player_names=[]
        ),
        app_context=app_context,
    )
    assert not result.details.removed
    assert path.read_bytes() == original


async def test_allowlist_api_reports_corrupt_disk_data(
    app_context, real_bedrock_server
):
    (Path(real_bedrock_server.server_dir) / "allowlist.json").write_text("broken")
    with pytest.raises(BSMError):
        await get_allowlist(
            GetAllowlistRequest(server_name=real_bedrock_server.server_name),
            app_context=app_context,
        )
