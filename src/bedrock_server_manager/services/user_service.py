# src/bedrock_server_manager/services/user_service.py
"""
Service managing user domain state mutations and user account operations.
"""

import time
from typing import TYPE_CHECKING, Awaitable, Callable, Literal, Optional

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError

from ..error import StorageError, UserInputError
from ..state.changeset import ChangeSet
from ..state.models import UserInfoState
from ..state.updates import UNSET, Unset, UserUpdate

if TYPE_CHECKING:
    from ..db.storage import Storage
    from ..state.app_state import AppState


class UserService:
    """Handles domain logic and mutations for user state."""

    def __init__(
        self,
        state: "AppState",
        storage: "Storage",
        revoke_connections: Callable[[str], Awaitable[None]] | None = None,
    ):
        self.state = state
        self.storage = storage
        self.revoke_connections = revoke_connections

    def get_user_state(self, username: str) -> Optional[UserInfoState]:
        """Retrieves a user state snapshot."""
        user = self.state.users.get(username)
        if user:
            res: UserInfoState = user.model_copy()
            return res
        return None

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
        """Registers or updates a user state record and marks dirty state."""
        async with self.state.users.get_lock(username):
            existing = self.state.users.get(username)
            values: dict[str, object] = {"username": username}
            for name, value in (
                ("role", role),
                ("theme", theme),
                ("is_active", is_active),
                ("id", user_id),
            ):
                if value is not None:
                    values[name] = value
            for field_name, nullable_value in (
                ("full_name", full_name),
                ("email", email),
            ):
                if nullable_value is not UNSET:
                    values[field_name] = nullable_value
            update = UserUpdate.model_validate(values)
            data = existing.model_dump() if existing else {}
            data.update(update.model_dump(exclude_unset=True))
            user = UserInfoState.model_validate(data)

            self.state.users.set(user)

        changeset = ChangeSet()
        changeset.add_user(username)

        await self.storage.apply_changeset(self.state, changeset)

        return user

    async def update_account(
        self,
        *,
        action: Literal["delete", "disable", "enable", "role", "theme", "profile"],
        user_id: int | None = None,
        username: str | None = None,
        values: dict[str, object] | None = None,
        actor_id: int | None = None,
    ) -> UserInfoState | None:
        """Commit an account mutation and its audit entry before publishing state."""
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
                        {"username": name, **(values or {})}
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
                if (
                    action in {"delete", "disable", "role"}
                    and self.revoke_connections is not None
                ):
                    await self.revoke_connections(name)
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
