# src/bedrock_server_manager/services/user_service.py
"""
Service managing user domain state mutations and user account operations.
"""

from typing import TYPE_CHECKING, Any, Optional

from ..state.changeset import ChangeSet
from ..state.models import UserInfoState

if TYPE_CHECKING:
    from ..context import AppContext


class UserService:
    """Handles domain logic and mutations for user state."""

    def __init__(
        self,
        app_context: Optional["AppContext"] = None,
        state: Optional[Any] = None,
        storage: Optional[Any] = None,
    ):
        self._app_context = app_context
        self._state = state
        self._storage = storage

    @property
    def app_context(self) -> Optional["AppContext"]:
        return self._app_context

    @property
    def state(self) -> Any:
        if self._state is not None:
            return self._state
        if self._app_context is not None:
            return self._app_context.state
        raise ValueError("UserService has no AppState provided or set via AppContext.")

    @property
    def storage(self) -> Optional[Any]:
        if self._storage is not None:
            return self._storage
        if (
            self._app_context is not None
            and getattr(self._app_context, "_storage", None) is not None
        ):
            return self._app_context.storage
        return None

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
        role: str = "user",
        theme: str = "default",
        is_active: bool = True,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> UserInfoState:
        """Registers or updates a user state record and marks dirty state."""
        existing = self.state.users.get(username)
        if existing:
            data = existing.model_dump()
            data["role"] = role
            data["theme"] = theme
            data["is_active"] = is_active
            if full_name is not None:
                data["full_name"] = full_name
            if email is not None:
                data["email"] = email
            if user_id is not None:
                data["id"] = user_id
            user = UserInfoState(**data)
        else:
            user = UserInfoState(
                id=user_id,
                username=username,
                role=role,
                theme=theme,
                is_active=is_active,
                full_name=full_name,
                email=email,
            )

        self.state.users.set(user)

        changeset = ChangeSet()
        changeset.add_user(username)

        if self.storage is not None and hasattr(self.storage, "apply_changeset"):
            await self.storage.apply_changeset(self.state, changeset)

        return user
