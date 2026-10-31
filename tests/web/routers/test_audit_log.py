"""
Integration tests for the audit_log router endpoints.
"""

import asyncio

from httpx2 import AsyncClient

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.db.models import User as UserModel


async def test_list_audit_logs_unauthorized(
    unauth_client: AsyncClient, test_admin_user
):
    """Test getting audit logs without authentication."""
    # Need to mock needs_setup because unauth_client doesn't create a user,
    # causing the auth middleware to trigger setup bypass.
    response = await unauth_client.get("/audit-log/list")
    assert response.status_code == 401


async def test_list_audit_logs_forbidden(auth_client: AsyncClient):
    """Test getting audit logs with standard user permissions."""
    response = await auth_client.get("/audit-log/list")
    assert response.status_code == 403


async def test_list_audit_logs_success(
    admin_auth_client: AsyncClient, app_context: AppContext, test_admin_user: UserModel
):
    """Test getting audit logs successfully with admin permissions."""
    # Create some dummy logs using the audit log repository
    async with app_context.storage.transaction() as session:
        await app_context.storage.audit_log_repo.create_audit_log(
            session, int(test_admin_user.id), "TEST_ACTION_1", {"key": "value1"}
        )
    await asyncio.sleep(0.1)  # ensure timestamps are different
    async with app_context.storage.transaction() as session:
        await app_context.storage.audit_log_repo.create_audit_log(
            session, int(test_admin_user.id), "TEST_ACTION_2", {"key": "value2"}
        )

    response = await admin_auth_client.get("/audit-log/list")
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


async def test_list_audit_logs_pagination(
    admin_auth_client: AsyncClient, app_context: AppContext, test_admin_user: UserModel
):
    """Test pagination with limit and offset query parameters."""
    async with app_context.storage.transaction() as session:
        for i in range(5):
            await app_context.storage.audit_log_repo.create_audit_log(
                session, int(test_admin_user.id), f"PAGED_ACTION_{i}"
            )

    # Test limit=2
    res_limit = await admin_auth_client.get("/audit-log/list?limit=2&offset=0")
    assert res_limit.status_code == 200
    page_1 = res_limit.json()
    assert len(page_1) == 2

    # Test offset=2
    res_offset = await admin_auth_client.get("/audit-log/list?limit=2&offset=2")
    assert res_offset.status_code == 200
    page_2 = res_offset.json()
    assert len(page_2) == 2

    # Pages must not overlap
    page_1_ids = {entry["id"] for entry in page_1}
    page_2_ids = {entry["id"] for entry in page_2}
    assert page_1_ids.isdisjoint(page_2_ids)

    # Test invalid limit constraint (> 500)
    res_invalid = await admin_auth_client.get("/audit-log/list?limit=501")
    assert res_invalid.status_code == 422
