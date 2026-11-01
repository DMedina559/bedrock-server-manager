"""Integration tests for the main router endpoints."""

from unittest.mock import patch

from httpx2 import AsyncClient


async def test_main_router_redirect_and_spa_serving(
    unauth_client: AsyncClient, tmp_path
):
    """Test root redirect, SPA index.html serving, missing frontend, and asset 404."""
    response = await unauth_client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307, 308)
    assert (
        response.headers["location"].endswith("/app")
        or response.headers["location"] == "/app"
    )

    assert (await unauth_client.get("/app/assets/style.css")).status_code == 404

    with patch("bsm_frontend.get_static_dir", return_value=str(tmp_path)):
        missing = await unauth_client.get("/app/")
        assert missing.status_code == 404 and "Frontend not found" in missing.text

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html><body>Test</body></html>")

    with patch("bsm_frontend.get_static_dir", return_value=str(static_dir)):
        for path in ("/app/", "/app/some/deep/path"):
            resp = await unauth_client.get(path)
            assert resp.status_code == 200
            assert "<html><body>Test</body></html>" in resp.text
