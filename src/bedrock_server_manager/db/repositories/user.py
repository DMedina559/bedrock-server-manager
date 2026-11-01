"""
Repository for managing User and RegistrationToken database entity persistence.
"""

import hashlib
from typing import List, Optional, cast

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...state.models import UserInfoState
from ..models import (
    AccountSecurity,
    AccountServerAccess,
    IntegrationToken,
    LoginSession,
    PasskeyChallenge,
    PasskeyCredential,
    RegistrationToken,
    ServerAccessGrant,
    TrustedDevice,
    User,
)


class UserRepository:
    """Handle database persistence for user accounts and registration tokens."""

    async def get_all_users(self, session: AsyncSession) -> List[UserInfoState]:
        """Return all users from the database as UserInfoState models."""
        result = await session.execute(select(User))
        users = []
        for u in result.scalars().all():
            u_name = str(u.username)
            u_info = UserInfoState.model_validate(
                {
                    "id": int(u.id),
                    "username": u_name,
                    "role": u.role,
                    "theme": str(u.theme or "default"),
                    "is_active": bool(u.is_active),
                    "full_name": str(u.full_name) if u.full_name else None,
                    "email": str(u.email) if u.email else None,
                }
            )
            users.append(u_info)
        return users

    async def get_user_by_username(
        self, session: AsyncSession, username: str
    ) -> Optional[User]:
        """Return a User SQLAlchemy model by username."""
        result = await session.execute(select(User).filter(User.username == username))
        return cast(Optional[User], result.scalar_one_or_none())

    async def get_user_by_id(
        self, session: AsyncSession, user_id: int
    ) -> Optional[User]:
        """Return a User SQLAlchemy model by user_id."""
        result = await session.execute(select(User).filter(User.id == user_id))
        return cast(Optional[User], result.scalar_one_or_none())

    async def save_user(self, session: AsyncSession, u_info: UserInfoState) -> None:
        """Persists or updates a single UserInfoState record."""
        user_record = await self.get_user_by_username(session, u_info.username)
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

    async def delete_user(self, session: AsyncSession, user: User) -> None:
        """Delete a User record from the database."""
        for model in (
            AccountSecurity,
            AccountServerAccess,
            IntegrationToken,
            LoginSession,
            PasskeyChallenge,
            PasskeyCredential,
            ServerAccessGrant,
            TrustedDevice,
        ):
            await session.execute(delete(model).where(model.owner_id == user.access_id))
        await session.delete(user)

    @staticmethod
    def digest_token(token: str) -> str:
        """Compute the SHA-256 hex digest of a raw token."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def get_registration_token(
        self, session: AsyncSession, token: str
    ) -> Optional[RegistrationToken]:
        """Return a RegistrationToken record by token string (matching its SHA-256 digest)."""
        digest = self.digest_token(token)
        result = await session.execute(
            select(RegistrationToken).filter(RegistrationToken.token_digest == digest)
        )
        return cast(Optional[RegistrationToken], result.scalar_one_or_none())

    async def get_registration_token_for_update(
        self, session: AsyncSession, token: str
    ) -> Optional[RegistrationToken]:
        """Lock the invitation row on databases supporting SELECT FOR UPDATE.

        SQLite ignores row locks; create_account also holds Storage.write_lock
        through validation, account creation and invitation deletion. That lock
        coordinates writers in one application process, not multiple workers.
        """
        digest = self.digest_token(token)
        result = await session.execute(
            select(RegistrationToken)
            .filter(RegistrationToken.token_digest == digest)
            .with_for_update()
        )
        return cast(Optional[RegistrationToken], result.scalar_one_or_none())

    async def create_registration_token(
        self, session: AsyncSession, token: str, role: str, expires: int
    ) -> RegistrationToken:
        """Create and add a new RegistrationToken record using its SHA-256 digest."""
        digest = self.digest_token(token)
        token_record = RegistrationToken(
            token_digest=digest, role=role, expires=expires
        )
        session.add(token_record)
        return token_record

    async def create_user(
        self, session: AsyncSession, username: str, hashed_password: str, role: str
    ) -> User:
        """Create and adds a new User record."""
        user = User(username=username, hashed_password=hashed_password, role=role)
        session.add(user)
        return user

    async def delete_registration_token(
        self, session: AsyncSession, token_record: RegistrationToken
    ) -> None:
        """Delete a RegistrationToken record from the database."""
        await session.delete(token_record)

    async def update_password(
        self, session: AsyncSession, username: str, hashed_password: str
    ) -> bool:
        """Updates hashed password for a user by username."""
        user = await self.get_user_by_username(session, username)
        if user:
            setattr(user, "hashed_password", hashed_password)
            return True
        return False

    async def count_active_admins(self, session: AsyncSession) -> int:
        """Counts active admin users in the database."""
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.role == "admin", User.is_active.is_(True))
        )
        return int(result.scalar() or 0)

    async def count_admins(self, session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count()).select_from(User).where(User.role == "admin")
        )
        return int(result.scalar() or 0)
