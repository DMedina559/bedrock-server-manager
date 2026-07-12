import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.web.deps.context import get_app_context


@pytest.fixture
def context_test_app(app_context):
    app = FastAPI()
    app.state.app_context = app_context

    @app.get("/test-context")
    async def get_context(ctx: AppContext = Depends(get_app_context)):
        # To verify we get the right context, we can just return a property that indicates it's valid
        # We can't easily serialize AppContext directly.
        return {"has_db": ctx.db is not None, "has_settings": ctx.settings is not None}

    return app


def test_get_app_context(context_test_app):
    """Test get_app_context dependency extracts AppContext from request.app.state."""
    client = TestClient(context_test_app)
    response = client.get("/test-context")
    assert response.status_code == 200
    data = response.json()
    assert data["has_db"] is True
    assert data["has_settings"] is True
