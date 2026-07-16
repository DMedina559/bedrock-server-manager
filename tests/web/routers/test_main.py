"""
Integration tests for the main router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_root_redirect(unauth_client: TestClient):
    """Test that the root URL redirects to the app."""
    response = unauth_client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307, 308)
    assert response.headers["location"] == "/app"


def test_serve_spa_real_file(unauth_client: TestClient, tmp_path):
    """Test serving the SPA index.html with a real temporary file."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    index_html = static_dir / "index.html"
    index_html.write_text("<html><body>Test</body></html>")

    with patch("bsm_frontend.get_static_dir", return_value=str(static_dir)):
        response = unauth_client.get("/app/")
        assert response.status_code == 200
        assert "<html><body>Test</body></html>" in response.text

        response2 = unauth_client.get("/app/some/deep/path")
        assert response2.status_code == 200
        assert "<html><body>Test</body></html>" in response2.text


def test_serve_spa_missing(unauth_client: TestClient, tmp_path):
    """Test serving the SPA when index.html is missing."""
    with patch("bsm_frontend.get_static_dir", return_value=str(tmp_path)):
        response = unauth_client.get("/app/")
        assert response.status_code == 404
        assert "Frontend not found" in response.text


def test_serve_spa_assets_404(unauth_client: TestClient):
    """Test that requests for assets directly through the SPA route return 404."""
    response = unauth_client.get("/app/assets/style.css")
    assert response.status_code == 404
