"""
Integration tests for the audit_log router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.web.routers.audit_log import create_audit_log


def test_list_audit_logs_unauthorized(unauth_client: TestClient):
    """Test getting audit logs without authentication."""
    # Need to mock needs_setup because unauth_client doesn't create a user,
    # causing the auth middleware to trigger setup bypass.
    with patch(
        "bedrock_server_manager.config.bcm_config.needs_setup", return_value=False
    ):
        response = unauth_client.get("/audit-log/list")
        assert response.status_code == 401


def test_list_audit_logs_forbidden(auth_client: TestClient):
    """Test getting audit logs with standard user permissions."""
    response = auth_client.get("/audit-log/list")
    assert response.status_code == 403


def test_list_audit_logs_success(
    admin_auth_client: TestClient, app_context: AppContext, test_admin_user: UserModel
):
    """Test getting audit logs successfully with admin permissions."""
    # Create some dummy logs using the router's helper function
    import time

    create_audit_log(
        app_context, test_admin_user.id, "TEST_ACTION_1", {"key": "value1"}
    )
    time.sleep(0.1)  # ensure timestamps are different
    create_audit_log(
        app_context, test_admin_user.id, "TEST_ACTION_2", {"key": "value2"}
    )

    response = admin_auth_client.get("/audit-log/list")
    assert response.status_code == 200

    data = response.json()
    assert len(data) >= 2

    # Check that our created logs are present
    actions = [log["action"] for log in data]
    assert "TEST_ACTION_1" in actions
    assert "TEST_ACTION_2" in actions

    # Check order (descending by timestamp)
    action_1_index = actions.index("TEST_ACTION_1")
    action_2_index = actions.index("TEST_ACTION_2")
    # 2 was created after 1, so it should be earlier in the list (lower index)
    assert action_2_index < action_1_index
