# bedrock_server_manager/web/routers/audit_log.py
"""
FastAPI router for viewing audit logs.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends

from ...context import AppContext
from ..deps import get_admin_user, get_app_context
from ..schemas import AuditLogResponse, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/audit-log",
    tags=["Audit Logs", "Application"],
)


async def create_audit_log(
    app_context: AppContext,
    user_id: int,
    action: str,
    details: Optional[Dict[Any, Any]] = None,
):
    """
    Creates an audit log entry.
    """
    async with app_context.storage.transaction() as session:
        await app_context.storage.audit_log_repo.create_audit_log(
            session, user_id=user_id, action=action, details=details
        )


@router.get("/list", response_model=List[AuditLogResponse])
async def list_audit_logs_api(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves audit logs as JSON.
    """
    async with app_context.storage.transaction() as session:
        logs = await app_context.storage.audit_log_repo.get_all_logs(session)
        return logs
