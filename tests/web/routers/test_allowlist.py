import json
from pathlib import Path

import pytest


async def test_allowlist_round_trip_persists_players(
    admin_auth_client, real_bedrock_server
):
    base = f"/api/server/{real_bedrock_server.server_name}/allowlist"
    response = await admin_auth_client.post(
        base + "/add", json={"players": ["Steve", "Alex"], "ignoresPlayerLimit": True}
    )
    assert response.status_code == 200
    response = await admin_auth_client.get(base + "/get")
    assert response.status_code == 200
    assert {p["name"] for p in response.json()["players"]} >= {"Steve", "Alex"}
    disk = json.loads(
        (Path(real_bedrock_server.paths.server_dir) / "allowlist.json").read_text()
    )
    assert all(p["ignoresPlayerLimit"] for p in disk if p["name"] in {"Steve", "Alex"})
    response = await admin_auth_client.request(
        "DELETE", base + "/remove", json={"players": ["Steve", "Missing"]}
    )
    assert response.status_code == 200
    assert "Steve" not in {
        p["name"]
        for p in (await admin_auth_client.get(base + "/get")).json()["players"]
    }
    assert "Steve" not in {
        p["name"] for p in await real_bedrock_server.allowlist.get_allowlist()
    }


@pytest.mark.parametrize(
    "method,suffix,payload",
    [
        ("POST", "/add", {"players": ["Steve"]}),
        ("GET", "/get", None),
        ("DELETE", "/remove", {"players": ["Steve"]}),
    ],
)
async def test_allowlist_requires_authentication(
    unauth_client, real_bedrock_server, method, suffix, payload
):
    response = await unauth_client.request(
        method,
        f"/api/server/{real_bedrock_server.server_name}/allowlist{suffix}",
        **({"json": payload} if payload else {}),
    )
    assert response.status_code == 401


async def test_allowlist_invalid_input_preserves_file(
    admin_auth_client, real_bedrock_server
):
    path = Path(real_bedrock_server.paths.server_dir) / "allowlist.json"
    original = path.read_bytes()
    response = await admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/allowlist/add",
        json={"players": "invalid"},
    )
    assert response.status_code in {400, 422}
    assert path.read_bytes() == original


async def test_allowlist_corrupt_file_returns_safe_error(
    admin_auth_client, real_bedrock_server
):
    path = Path(real_bedrock_server.paths.server_dir) / "allowlist.json"
    path.write_text("private broken JSON")
    response = await admin_auth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/allowlist/get"
    )
    assert response.status_code == 500
    assert "private broken JSON" not in response.text
