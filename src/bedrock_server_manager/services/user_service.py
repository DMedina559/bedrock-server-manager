# src/bedrock_server_manager/services/user_service.py
"""
Service managing user domain state mutations and user account operations.
"""

from typing import TYPE_CHECKING, Optional

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
    ):
        self.state = state
        self.storage = storage

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
