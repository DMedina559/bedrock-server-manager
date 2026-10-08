import pytest


async def test_server_dependency_accepts_actual_installation(
    admin_auth_client, real_bedrock_server
):
    response = await admin_auth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/properties/get"
    )
    assert response.status_code == 200


@pytest.mark.parametrize("name", ["missing_server", "missing@server"])
async def test_server_dependency_rejects_missing_or_invalid_names(
    admin_auth_client, name
):
    response = await admin_auth_client.get(f"/api/server/{name}/properties/get")
    assert response.status_code in {400, 404}
    assert "error" in response.json()
