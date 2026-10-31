# src/bedrock_server_manager/services/user_service.py
"""
Service managing user domain state mutations and user account operations.
"""

import time
from typing import TYPE_CHECKING, Awaitable, Callable, Literal, Optional

from pydantic import JsonValue, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError

from ..contracts import CommittedMutationResult, NewPassword
from ..error import IncompleteOperationError, StorageError, UserInputError
from ..failures import classify_failure
from ..state.changeset import ChangeSet
from ..state.models import UserInfoState
from ..state.updates import UNSET, AccountPatch, Unset, UserUpdate

if TYPE_CHECKING:
    from ..db.storage import Storage
    from ..state.app_state import AppState


class UserService:
    """Handle domain logic and mutations for user state."""

    def __init__(
        self,
        state: "AppState",
        storage: "Storage",
        revoke_connections: Callable[[str], Awaitable[None]] | None = None,
        credentials_changed: Callable[[str], Awaitable[None]] | None = None,
        security_event: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        self.state = state
        self.storage = storage
        self.revoke_connections = revoke_connections
        self.credentials_changed = credentials_changed
        self.security_event = security_event

    def get_user_state(self, username: str) -> Optional[UserInfoState]:
        """Return a user state snapshot."""
        user = self.state.users.get(username)
        if user:
            res: UserInfoState = user.model_copy()
            return res
        return None

    async def list_users(self) -> list[UserInfoState]:
        """Return all users from persistent storage."""
        async with self.storage.transaction() as session:
            return await self.storage.user_repo.get_all_users(session)

    async def change_password(
        self,
        username: str,
        current_password: str,
        new_password: str,
        *,
        keep_session_id: str | None = None,
    ) -> bool:
        """Verify current password and update hashed password for a user."""
        try:
            new_password = (
                TypeAdapter(NewPassword)
                .validate_python(new_password)
                .get_secret_value()
            )
        except ValidationError:
            raise UserInputError(
                "Use a less common passphrase of at least 15 characters (up to 1024 UTF-8 bytes)."
            ) from None
        from ..web.auth import get_password_hash_async, verify_password_async

        async with self.storage.transaction() as session:
            db_user = await self.storage.user_repo.get_user_by_username(
                session, username
            )
            if not db_user:
                return False
            if not await verify_password_async(
                current_password, str(db_user.hashed_password)
            ):
                raise UserInputError("Incorrect current password.")
            hashed_pwd = await get_password_hash_async(new_password)
            from sqlalchemy import update

            from ..db.models import LoginSession, User

            changed = await session.execute(
                update(User)
                .where(
                    User.id == db_user.id, User.auth_revision == db_user.auth_revision
                )
                .values(
                    hashed_password=hashed_pwd, auth_revision=User.auth_revision + 1
                )
            )
            if getattr(changed, "rowcount", None) != 1:
                raise UserInputError("Account credentials changed; try again")
            query = update(LoginSession).where(
                LoginSession.owner_id == db_user.access_id,
                LoginSession.revoked_at.is_(None),
            )
            if keep_session_id:
                query = query.where(LoginSession.id != keep_session_id)
            await session.execute(query.values(revoked_at=int(time.time())))
            from .session_service import SessionService

            SessionService.add_event(session, db_user.access_id, "password_changed")
        if self.credentials_changed:
            await self.credentials_changed(db_user.access_id)
        if self.security_event:
            await self.security_event(db_user.access_id, "password_changed")
        return True

    async def reset_password(self, username: str, new_password: str) -> bool:
        """Reset hashed password for a user without verifying old password."""
        from sqlalchemy import update

        from ..db.models import LoginSession, User
        from ..web.auth import get_password_hash_async
        from .session_service import SessionService

        async with self.storage.transaction() as session:
            user = await self.storage.user_repo.get_user_by_username(session, username)
            if user is None:
                return False
            try:
                new_password = (
                    TypeAdapter(NewPassword)
                    .validate_python(new_password)
                    .get_secret_value()
                )
            except ValidationError:
                raise UserInputError(
                    "Use a less common passphrase of at least 15 characters (up to 1024 UTF-8 bytes)."
                ) from None
            hashed_pwd = await get_password_hash_async(new_password)
            changed = await session.execute(
                update(User)
                .where(User.id == user.id, User.auth_revision == user.auth_revision)
                .values(
                    hashed_password=hashed_pwd, auth_revision=User.auth_revision + 1
                )
            )
            if getattr(changed, "rowcount", None) != 1:
                raise UserInputError("Account credentials changed; try again")
            await session.execute(
                update(LoginSession)
                .where(
                    LoginSession.owner_id == user.access_id,
                    LoginSession.revoked_at.is_(None),
                )
                .values(revoked_at=int(time.time()))
            )
            SessionService.add_event(session, user.access_id, "password_reset")
        if self.credentials_changed:
            await self.credentials_changed(user.access_id)
        if self.security_event:
            await self.security_event(user.access_id, "password_reset")
        return True

    async def create_registration_token(
        self, role: str, ttl_seconds: int = 86400
    ) -> str:
        """Generate and persist a new registration token."""
        import secrets

        token = secrets.token_urlsafe(32)
        expires = int(time.time()) + ttl_seconds
        async with self.storage.transaction() as session:
            await self.storage.user_repo.create_registration_token(
                session, token=token, role=role, expires=expires
            )
        return token

    async def validate_registration_token(self, token: str) -> bool:
        """Return True if a registration token exists and has not expired."""
        async with self.storage.transaction() as session:
            registration_token = await self.storage.user_repo.get_registration_token(
                session, token
            )
            return bool(
                registration_token
                and registration_token.expires is not None
                and registration_token.expires >= int(time.time())
            )

    async def register_or_update_user(
        self,
        username: str,
        role: Optional[str] = None,
        theme: Optional[str] = None,
        is_active: Optional[bool] = None,
        full_name: str | None | Unset = UNSET,
        email: str | None | Unset = UNSET,
        user_id: Optional[int] = None,
    ) -> UserInfoState:
        """Register or updates a user state record and marks dirty state."""
        values: dict[str, object] = {"username": username}
        for name, value in (
            ("role", role),
            ("theme", theme),
            ("is_active", is_active),
            ("id", user_id),
        ):
            if value is not None:
                values[name] = value
        for nullable_name, nullable_value in (
            ("full_name", full_name),
            ("email", email),
        ):
            if nullable_value is not UNSET:
                values[nullable_name] = nullable_value
        return await self.apply_update(UserUpdate.model_validate(values))

    async def apply_update(self, request: UserUpdate) -> UserInfoState:
        request = UserUpdate.model_validate(request)

        def build(existing: UserInfoState | None) -> UserInfoState:
            data = existing.model_dump() if existing else {}
            data.update(request.model_dump(exclude_unset=True))
            return UserInfoState.model_validate(data)

        changeset = ChangeSet()
        changeset.add_user(request.username)
        return await self.storage.commit_record(
            self.state,
            changeset,
            request.username,
            get_lock=self.state.users.get_lock,
            get=self.state.users.get,
            build=build,
            save=self.storage.user_repo.save_user,
            publish=self.state.users.set,
            acknowledge=self.state.users.remove_dirty_user,
        )

    async def update_account(
        self,
        *,
        action: Literal["delete", "disable", "enable", "role", "theme", "profile"],
        user_id: int | None = None,
        username: str | None = None,
        values: AccountPatch | None = None,
        actor_id: int | None = None,
    ) -> UserInfoState | None:
        """Commit an account mutation and its audit entry before publishing state."""
        patch_request = (
            AccountPatch.model_validate(values)
            if values is not None
            else AccountPatch()
        )
        allowed = {
            "delete": set(),
            "disable": set(),
            "enable": set(),
            "role": {"role"},
            "theme": {"theme"},
            "profile": {"full_name", "email"},
        }
        if patch_request.model_fields_set - allowed[action]:
            raise UserInputError("Patch fields do not match the account action.")
        if action in {"role", "theme"} and getattr(patch_request, action) is None:
            raise UserInputError(f"Account {action} is required.")
        async with self.storage.write_lock:
            async with self.storage.db.session_manager() as session:
                user = (
                    await self.storage.user_repo.get_user_by_id(session, user_id)
                    if user_id is not None
                    else await self.storage.user_repo.get_user_by_username(
                        session, username or ""
                    )
                )
                if user is None:
                    return None
                name = user.username
                if name is None:
                    raise UserInputError("Account has no username.")
            async with self.state.users.get_lock(name):
                async with self.storage.transaction() as session:
                    user = await self.storage.user_repo.get_user_by_username(
                        session, name
                    )
                    if user is None:
                        return None
                    update = UserUpdate.model_validate(
                        {
                            "username": name,
                            **patch_request.model_dump(exclude_unset=True),
                        }
                    )
                    patch = update.model_dump(
                        exclude_unset=True, exclude={"username", "id"}
                    )
                    if action == "disable":
                        patch["is_active"] = False
                    elif action == "enable":
                        patch["is_active"] = True
                    removes_admin = action in {"delete", "disable"} or (
                        action == "role" and patch.get("role") != "admin"
                    )
                    if user.role == "admin" and user.is_active and removes_admin:
                        if (
                            await self.storage.user_repo.count_active_admins(session)
                            <= 1
                        ):
                            verb = {
                                "delete": "delete",
                                "disable": "disable",
                                "role": "change the role of",
                            }[action]
                            raise UserInputError(
                                f"Cannot {verb} the last active admin."
                            )
                    details: dict[str, JsonValue] = {
                        "user_id": user.id,
                        "username": name,
                    }
                    if action == "role":
                        details.update(original_role=user.role, new_role=patch["role"])
                    for field, value in patch.items():
                        setattr(user, field, value)
                    if action in {"disable", "enable", "role"}:
                        from sqlalchemy import update as sql_update

                        from ..db.models import LoginSession

                        user.auth_revision += 1
                        await session.execute(
                            sql_update(LoginSession)
                            .where(
                                LoginSession.owner_id == user.access_id,
                                LoginSession.revoked_at.is_(None),
                            )
                            .values(revoked_at=int(time.time()), verified_at=0)
                        )
                    if action in {"disable", "enable", "role"}:
                        from .session_service import SessionService

                        SessionService.add_event(
                            session,
                            user.access_id,
                            {
                                "disable": "account_disabled",
                                "enable": "account_enabled",
                                "role": "role_changed",
                            }[action],
                        )
                    record = UserInfoState.model_validate(user, from_attributes=True)
                    if actor_id is not None:
                        await self.storage.audit_log_repo.create_audit_log(
                            session,
                            actor_id,
                            (
                                "update_user_role"
                                if action == "role"
                                else action + "_user"
                            ),
                            details,
                        )
                    if action == "delete":
                        await self.storage.user_repo.delete_user(session, user)
                # No live state changes until both account and audit commit.
                if action == "delete":
                    self.state.users.remove(name)
                else:
                    cached = self.state.users.get(name)
                    dirty = name in self.state.users.dirty_users
                    if cached is not None and dirty:
                        data = cached.model_dump()
                        data.update(patch)
                        data["id"] = record.id
                        record = UserInfoState.model_validate(data)
                    self.state.users.set(record)
                    if not dirty:
                        self.state.users.remove_dirty_user(name)
        if action in {"disable", "enable", "role"} and self.security_event:
            await self.security_event(
                user.access_id,
                {
                    "disable": "account_disabled",
                    "enable": "account_enabled",
                    "role": "role_changed",
                }[action],
            )
        if (
            action in {"delete", "disable", "role"}
            and self.revoke_connections is not None
        ):
            try:
                await self.revoke_connections(name)
            except Exception as error:
                raise IncompleteOperationError(
                    "Account mutation committed, but connection revocation failed.",
                    CommittedMutationResult(
                        action=action,
                        resource=name,
                        recovery_error=classify_failure(error).error,
                    ),
                ) from error
        return record

    async def create_account(
        self,
        username: str,
        hashed_password: str,
        *,
        token: str | None = None,
        first_admin: bool = False,
    ) -> UserInfoState | None:
        """Consume registration and publish the new account only after commit."""
        try:
            async with self.storage.write_lock:
                async with self.state.users.get_lock(username):
                    async with self.storage.transaction() as session:
                        registration = None
                        role: str | None
                        if first_admin:
                            if await self.storage.user_repo.count_admins(session):
                                raise UserInputError(
                                    "Application has already been set up."
                                )
                            role = "admin"
                        else:
                            registration = (
                                await self.storage.user_repo.get_registration_token(
                                    session, token or ""
                                )
                            )
                            if (
                                registration is None
                                or registration.expires is None
                                or registration.expires <= int(time.time())
                            ):
                                return None
                            role = registration.role
                        candidate = UserInfoState.model_validate(
                            {"username": username, "role": role}
                        )
                        user = await self.storage.user_repo.create_user(
                            session, username, hashed_password, candidate.role
                        )
                        await session.flush()
                        record = UserInfoState.model_validate(
                            user, from_attributes=True
                        )
                        if registration is not None:
                            await self.storage.user_repo.delete_registration_token(
                                session, registration
                            )
                    self.state.users.set(record)
                    self.state.users.remove_dirty_user(username)
                    return record
        except StorageError as error:
            if isinstance(error.__cause__, IntegrityError):
                raise UserInputError(
                    "Username already exists. Please choose a different one."
                ) from error
            raise
