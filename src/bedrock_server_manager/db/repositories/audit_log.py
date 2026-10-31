"""
Repository for managing AuditLog database entity operations.
"""

from typing import List

from pydantic import Field, JsonValue
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...state.models import PersistentRecord
from ..models import AuditLog


class AuditEntry(PersistentRecord):
    user_id: int = Field(gt=0)
    action: str = Field(min_length=1)
    details: dict[str, JsonValue] | None = None


class AuditLogRepository:
    """Handle database persistence for audit log records."""

    async def create_audit_log(
        self,
        session: AsyncSession,
        user_id: int,
        action: str,
        details: dict[str, JsonValue] | None = None,
    ) -> AuditLog:
        """Create and adds an audit log entry to the session."""
        entry = AuditEntry(user_id=user_id, action=action, details=details)
        log = AuditLog(**entry.model_dump(mode="json"))
        session.add(log)
        return log

    async def get_all_logs(
        self, session: AsyncSession, limit: int | None = None, offset: int = 0
    ) -> List[AuditLog]:
        """Return audit logs ordered deterministically by timestamp and id descending."""
        query = select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        if offset > 0:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())
