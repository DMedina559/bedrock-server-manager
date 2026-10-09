import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetPermissionsRequest,
    SetPermissionsRequest,
)
from bedrock_server_manager.api.permissions import get_permissions, set_permissions


async def test_permission_api_updates_real_file(app_context, real_bedrock_server):
    name = real_bedrock_server.server_name
    for level in ("operator", "member", "visitor"):
        response = await set_permissions(
            SetPermissionsRequest(
                server_name=name, xuid="123", player_name="Player", permission=level
            ),
            app_context=app_context,
        )
        assert response.status == "success"
        result = await get_permissions(
            GetPermissionsRequest(server_name=name), app_context=app_context
        )
        assert (
            next(p for p in result.permissions if p.xuid == "123").permission_level
            == level
        )


@pytest.mark.parametrize(
    "field,value", [("server_name", ""), ("xuid", ""), ("permission", "invalid")]
)
def test_permission_request_validation(field, value):
    payload = {
        "server_name": "test_server",
        "xuid": "123",
        "player_name": "Player",
        "permission": "member",
        field: value,
    }
    with pytest.raises(ValidationError):
        SetPermissionsRequest.model_validate(payload)
