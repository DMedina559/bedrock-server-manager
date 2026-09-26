"""
Repository for managing User and RegistrationToken database entity persistence.
"""

from typing import Any, List, Optional, cast

from sqlalchemy import func
from sqlalchemy.future import select

from ...state.models import UserInfoState
from ..models import RegistrationToken, User


class UserRepository:
    """Handles database persistence for user accounts and registration tokens."""

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

    async def get_user_by_username(self, session: Any, username: str) -> Optional[User]:
        """Retrieves a User SQLAlchemy model by username."""
        result = await session.execute(select(User).filter(User.username == username))
        return cast(Optional[User], result.scalar_one_or_none())

    async def get_user_by_id(self, session: Any, user_id: int) -> Optional[User]:
        """Retrieves a User SQLAlchemy model by user_id."""
        result = await session.execute(select(User).filter(User.id == user_id))
        return cast(Optional[User], result.scalar_one_or_none())

    async def save_user(self, session: Any, u_info: UserInfoState) -> None:
        """Persists or updates a single UserInfoState record."""
        user_record: Any = await self.get_user_by_username(session, u_info.username)
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

    async def delete_user(self, session: Any, user: User) -> None:
        """Deletes a User record from the database."""
        await session.delete(user)

    async def get_registration_token(
        self, session: Any, token: str
    ) -> Optional[RegistrationToken]:
        """Retrieves a RegistrationToken record by token string."""
        result = await session.execute(
            select(RegistrationToken).filter(RegistrationToken.token == token)
        )
        return cast(Optional[RegistrationToken], result.scalar_one_or_none())

    async def create_registration_token(
        self, session: Any, token: str, role: str, expires: int
    ) -> RegistrationToken:
        """Creates and adds a new RegistrationToken record."""
        token_record = RegistrationToken(token=token, role=role, expires=expires)
        session.add(token_record)
        return token_record

    async def create_user(
        self, session: Any, username: str, hashed_password: str, role: str
    ) -> User:
        """Creates and adds a new User record."""
        user = User(username=username, hashed_password=hashed_password, role=role)
        session.add(user)
        return user

    async def delete_registration_token(
        self, session: Any, token_record: RegistrationToken
    ) -> None:
        """Deletes a RegistrationToken record from the database."""
        await session.delete(token_record)

    async def update_password(
        self, session: Any, username: str, hashed_password: str
    ) -> bool:
        """Updates hashed password for a user by username."""
        user = await self.get_user_by_username(session, username)
        if user:
            user.hashed_password = hashed_password
            return True
        return False

    async def count_active_admins(self, session: Any) -> int:
        """Counts active admin users in the database."""
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.role == "admin", User.is_active.is_(True))
        )
        return int(result.scalar() or 0)
