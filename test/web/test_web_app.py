import pytest
from fastapi.testclient import TestClient


def test_read_main(client: TestClient):
    """Test that the main page loads."""
    response = client.get("/")
    assert response.status_code == 200


def test_static_files(client: TestClient):
    """Test that static files are served."""
    response = client.get("/static/css/base.css")
    assert response.status_code == 200


def test_openapi_json(client: TestClient, authenticated_user):
    """Test that the OpenAPI JSON is available."""
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Bedrock Server Manager"


def test_swagger_ui(client: TestClient):
    """Test that the Swagger UI is available."""
    response = client.get("/docs")
    assert response.status_code == 200
