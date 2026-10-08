"""HTTP input models reject values before executing an operation."""

import pytest
from pydantic import ValidationError

from bedrock_server_manager.web.schemas import (
    GenerateTokenPayload,
    PluginStatusSetPayload,
    PropertiesPayload,
    ServerSettingItemPayload,
    UpdateUserRolePayload,
)


@pytest.mark.parametrize(
    "model,data",
    [
        (UpdateUserRolePayload, {"role": "superadmin"}),
        (UpdateUserRolePayload, {"role": "user", "typo": True}),
        (GenerateTokenPayload, {"role": "owner"}),
        (PluginStatusSetPayload, {"enabled": "true"}),
        (PropertiesPayload, {"properties": {"max-players": 10}}),
        (ServerSettingItemPayload, {"key": "custom.a", "value": float("nan")}),
    ],
)
def test_http_inputs_reject_invalid_data(model, data):
    with pytest.raises(ValidationError):
        model.model_validate(data)


async def test_unknown_role_rejected_by_http_before_write(admin_auth_client):
    response = admin_auth_client.post("/api/users/1/role", json={"role": "owner"})
    assert response.status_code == 422
