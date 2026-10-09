from pathlib import Path


async def test_custom_panorama_serves_real_file(unauth_client, app_context):
    panorama = Path(app_context.settings.config_dir) / "panorama.jpeg"
    panorama.write_bytes(b"custom image")
    response = await unauth_client.get("/api/panorama")
    assert response.status_code == 200
    assert response.content == panorama.read_bytes()
    assert response.headers["content-type"] == "image/jpeg"


async def test_panorama_falls_back_to_configured_assets(
    unauth_client, tmp_path, monkeypatch
):
    assets = tmp_path / "assets"
    image = assets / "image" / "panorama.jpeg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"default image")
    monkeypatch.setattr(
        "bedrock_server_manager.web.routers.util.STATIC_DIR", str(assets)
    )
    response = await unauth_client.get("/api/panorama")
    assert response.status_code == 200
    assert response.content == image.read_bytes()
    image.unlink()
    response = await unauth_client.get("/api/panorama")
    assert response.status_code == 404
