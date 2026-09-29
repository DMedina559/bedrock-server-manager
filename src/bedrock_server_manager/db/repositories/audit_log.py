"""
Repository for managing AuditLog database entity operations.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.future import select

from ..models import AuditLog


class AuditLogRepository:
    """Handles database persistence for audit log records."""

    def __init__(self, db: Any = None):
        self.db = db

    async def create_audit_log(
        self,
        session: Any,
        user_id: int,
        action: str,
        details: Optional[Dict[Any, Any]] = None,
    ) -> AuditLog:
        """Creates and adds an audit log entry to the session."""
        log = AuditLog(user_id=user_id, action=action, details=details)
        session.add(log)
        return log

    async def get_all_logs(self, session: Any) -> List[AuditLog]:
        """Retrieves all audit logs ordered by timestamp descending."""
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.timestamp.desc())
        )
        return list(result.scalars().all())
