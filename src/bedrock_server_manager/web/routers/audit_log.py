# bedrock_server_manager/web/routers/audit_log.py
"""
FastAPI router for viewing audit logs.
"""
import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from ...db.models import AuditLog
from ..templating import templates
from ..auth_utils import get_admin_user
from ..schemas import User as UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/audit-log",
    tags=["Audit Log"],
)


def create_audit_log(app_context, user_id: int, action: str, details: dict = None):
    """
    Creates an audit log entry.
    """
    with app_context.db.session_manager() as db:
        log = AuditLog(user_id=user_id, action=action, details=details)
        db.add(log)
        db.commit()


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def audit_log_page(
    request: Request,
    current_user: UserSchema = Depends(get_admin_user),
):
    """
    Serves the audit log page.
    """
    with request.app.state.app_context.db.session_manager() as db:
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    return templates.TemplateResponse(
        request,
        "audit_log.html",
        {"request": request, "logs": logs, "current_user": current_user},
    )
