# bedrock_server_manager/web/routers/audit_log.py
"""
FastAPI router for viewing audit logs.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...context import AppContext
from ...db.models import AuditLog
from ..auth_utils import get_admin_user
from ..dependencies import get_app_context, get_templates
from ..schemas import User as UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/audit-log",
    tags=["Audit Log"],
)


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


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def audit_log_page(
    request: Request,
    current_user: UserSchema = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the audit log page.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    return templates.TemplateResponse(
        request,
        "audit_log.html",
        {"logs": logs, "current_user": current_user},
    )
