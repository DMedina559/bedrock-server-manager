"""
Integration tests for the main router endpoints.
"""

from unittest.mock import patch

from httpx2 import AsyncClient


async def test_root_redirect(unauth_client: AsyncClient):
    """Test that the root URL redirects to the app."""
    response = await unauth_client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307, 308)
    assert (
        response.headers["location"].endswith("/app")
        or response.headers["location"] == "/app"
    )


async def test_serve_spa_real_file(unauth_client: AsyncClient, tmp_path):
    """Test serving the SPA index.html with a real temporary file."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    index_html = static_dir / "index.html"
    index_html.write_text("<html><body>Test</body></html>")

    with patch("bsm_frontend.get_static_dir", return_value=str(static_dir)):
        response = await unauth_client.get("/app/")
        assert response.status_code == 200
        assert "<html><body>Test</body></html>" in response.text

        response2 = await unauth_client.get("/app/some/deep/path")
        assert response2.status_code == 200
        assert "<html><body>Test</body></html>" in response2.text


async def test_serve_spa_missing(unauth_client: AsyncClient, tmp_path):
    """Test serving the SPA when index.html is missing."""
    with patch("bsm_frontend.get_static_dir", return_value=str(tmp_path)):
        response = await unauth_client.get("/app/")
        assert response.status_code == 404
        assert "Frontend not found" in response.text


async def test_serve_spa_assets_404(unauth_client: AsyncClient):
    """Test that requests for assets directly through the SPA route return 404."""
    response = await unauth_client.get("/app/assets/style.css")
    assert response.status_code == 404
