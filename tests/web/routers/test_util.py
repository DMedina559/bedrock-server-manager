from pathlib import Path


async def test_panorama_custom_and_fallback_assets(
    unauth_client, app_context, tmp_path, monkeypatch
):
    panorama = Path(app_context.settings.config_dir) / "panorama.jpeg"
    panorama.write_bytes(b"custom image")
    response = await unauth_client.get("/api/panorama")
    assert response.status_code == 200
    assert response.content == b"custom image"
    assert response.headers["content-type"] == "image/jpeg"
    panorama.unlink()

    assets = tmp_path / "assets"
    image = assets / "image" / "panorama.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"default image")
    monkeypatch.setattr(
        "bedrock_server_manager.web.routers.util.STATIC_DIR", str(assets)
    )
    response = await unauth_client.get("/api/panorama")
    assert response.status_code == 200
    assert response.content == b"default image"
    assert response.headers["content-type"] == "image/png"
    image.unlink()
    response = await unauth_client.get("/api/panorama")
    assert response.status_code == 404
