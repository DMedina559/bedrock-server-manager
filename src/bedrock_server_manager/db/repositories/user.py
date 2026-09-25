"""
Repository for managing User database entity persistence.
"""

from typing import Any, List

from sqlalchemy.future import select

from ...state.models import UserInfoState
from ..models import User


class UserRepository:
    """Handles database persistence for user accounts."""

    def __init__(self, db: Any = None):
        self.db = db

    async def get_all_users(self, session: Any) -> List[UserInfoState]:
        """Retrieves all users from the database as UserInfoState models."""
        result = await session.execute(select(User))
        users = []
        for u in result.scalars().all():
            u_name = str(u.username)
            u_info = UserInfoState(
                id=int(u.id),
                username=u_name,
                role=str(u.role),
                theme=str(u.theme),
                is_active=bool(u.is_active),
                full_name=str(u.full_name) if u.full_name else None,
                email=str(u.email) if u.email else None,
            )
            users.append(u_info)
        return users

    async def save_user(self, session: Any, u_info: UserInfoState) -> None:
        """Persists or updates a single UserInfoState record."""
        result = await session.execute(select(User).filter_by(username=u_info.username))
        user_record = result.scalars().first()
        if user_record:
            user_record.role = u_info.role
            user_record.theme = u_info.theme
            user_record.is_active = u_info.is_active
            user_record.full_name = u_info.full_name
            user_record.email = u_info.email
        else:
            user_record = User(
                username=u_info.username,
                role=u_info.role,
                theme=u_info.theme,
                is_active=u_info.is_active,
                full_name=u_info.full_name,
                email=u_info.email,
            )
            session.add(user_record)
