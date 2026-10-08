import json
from pathlib import Path

import pytest


async def test_permission_update_round_trip(admin_auth_client, real_bedrock_server):
    base = f"/api/server/{real_bedrock_server.server_name}/permissions"
    players = [
        {"xuid": "123", "name": "Player1", "permission_level": "operator"},
        {"xuid": "456", "name": "Player2", "permission_level": "visitor"},
    ]
    response = await admin_auth_client.post(
        base + "/set", json={"permissions": players}
    )
    assert response.status_code == 200
    entries = (await admin_auth_client.get(base + "/get")).json()["permissions"]
    assert {p["xuid"]: p["permission_level"] for p in entries} == {
        "123": "operator",
        "456": "visitor",
    }
    disk = json.loads(
        (Path(real_bedrock_server.server_dir) / "permissions.json").read_text()
    )
    assert {p["xuid"]: p["permission"] for p in disk} == {
        "123": "operator",
        "456": "visitor",
    }


@pytest.mark.parametrize("permission", ["invalid", 1, None])
async def test_invalid_permission_preserves_disk(
    admin_auth_client, real_bedrock_server, permission
):
    path = Path(real_bedrock_server.server_dir) / "permissions.json"
    original = path.read_bytes()
    response = await admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/permissions/set",
        json={
            "permissions": [
                {"xuid": "123", "name": "Player1", "permission_level": permission}
            ]
        },
    )
    assert response.status_code in {400, 422}
    assert path.read_bytes() == original


@pytest.mark.parametrize("authenticated,expected", [(False, 401), (True, 403)])
async def test_permission_changes_require_moderator(
    unauth_client, auth_client, real_bedrock_server, authenticated, expected
):
    client = auth_client if authenticated else unauth_client
    response = await client.post(
        f"/api/server/{real_bedrock_server.server_name}/permissions/set",
        json={
            "permissions": [
                {"xuid": "123", "name": "Player1", "permission_level": "operator"}
            ]
        },
    )
    assert response.status_code == expected


async def test_missing_permissions_file_returns_empty_permissions(
    admin_auth_client, real_bedrock_server
):
    (Path(real_bedrock_server.server_dir) / "permissions.json").unlink()
    response = await admin_auth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/permissions/get"
    )
    assert response.status_code == 200
    assert response.json()["permissions"] == []
