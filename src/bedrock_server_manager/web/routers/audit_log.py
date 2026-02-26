# bedrock_server_manager/web/routers/audit_log.py
"""
FastAPI router for viewing audit logs.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from ...context import AppContext
from ...db.models import AuditLog
from ..auth_utils import get_admin_user
from ..dependencies import get_app_context
from ..schemas import User as UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/audit-log",
    tags=["Audit Log"],
)


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


def create_audit_log(
    app_context,
    user_id: int,
    action: str,
    details: Optional[Dict[Any, Any]] = None,
):
    """
    Creates an audit log entry.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        log = AuditLog(user_id=user_id, action=action, details=details)
        db.add(log)
        db.commit()


@router.get("/list", response_model=List[AuditLogResponse])
async def list_audit_logs_api(
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves audit logs as JSON.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
        # Convert timestamp to string if needed, or Pydantic handles datetime
        return logs
