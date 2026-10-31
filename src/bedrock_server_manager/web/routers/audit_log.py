"""
FastAPI router for viewing audit logs.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, Security

from ...context import AppContext
from ..access_policy import Permission
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import AuditLogResponse, UserResponse

# bedrock_server_manager/web/routers/audit_log.py


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-log", tags=["Audit Logs"])


@router.get(
    "/list", operation_id="list_audit_logs", response_model=List[AuditLogResponse]
)
async def list_audit_logs_api(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.AUDIT_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> List[AuditLogResponse]:
    """Return audit logs as JSON."""
    async with app_context.storage.transaction() as session:
        logs = await app_context.storage.audit_log_repo.get_all_logs(session)
        return [
            AuditLogResponse.model_validate(log, from_attributes=True) for log in logs
        ]
