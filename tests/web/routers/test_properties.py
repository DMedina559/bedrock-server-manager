from pathlib import Path

import pytest


async def test_properties_round_trip_persists_user_values(
    admin_auth_client, real_bedrock_server
):
    base = f"/api/server/{real_bedrock_server.server_name}/properties"
    response = await admin_auth_client.post(
        base + "/set",
        json={"properties": {"server-name": "Integration Server", "max-players": "25"}},
    )
    assert response.status_code == 200
    result = (await admin_auth_client.get(base + "/get")).json()
    assert result["properties"]["server-name"] == "Integration Server"
    assert result["properties"]["max-players"] == "25"
    text = (
        Path(real_bedrock_server.paths.server_dir) / "server.properties"
    ).read_text()
    assert "server-name=Integration Server" in text
    assert (
        await real_bedrock_server.properties.get_server_property("server-name")
        == "Integration Server"
    )


@pytest.mark.parametrize("value", ["0", "65536", "invalid"])
async def test_invalid_property_update_preserves_disk(
    admin_auth_client, real_bedrock_server, value
):
    path = Path(real_bedrock_server.paths.server_dir) / "server.properties"
    original = path.read_bytes()
    response = await admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/properties/set",
        json={"properties": {"server-port": value}},
    )
    assert response.status_code in {400, 422}
    assert path.read_bytes() == original


@pytest.mark.parametrize("authenticated,expected", [(False, 401), (True, 403)])
async def test_property_changes_require_admin(
    unauth_client, auth_client, real_bedrock_server, authenticated, expected
):
    client = auth_client if authenticated else unauth_client
    response = await client.post(
        f"/api/server/{real_bedrock_server.server_name}/properties/set",
        json={"properties": {"server-name": "Denied"}},
    )
    assert response.status_code == expected


async def test_missing_properties_returns_not_found(
    admin_auth_client, real_bedrock_server
):
    (Path(real_bedrock_server.paths.server_dir) / "server.properties").unlink()
    response = await admin_auth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/properties/get"
    )
    assert response.status_code == 404
