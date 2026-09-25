# src/bedrock_server_manager/services/user_service.py
"""
Service managing user domain state mutations and user account operations.
"""

from typing import TYPE_CHECKING, Optional

from ..state.models import UserInfoState

if TYPE_CHECKING:
    from ..context import AppContext


class UserService:
    """Handles domain logic and mutations for user state."""

    def __init__(self, app_context: "AppContext"):
        self.app_context = app_context

    def get_user_state(self, username: str) -> Optional[UserInfoState]:
        """Retrieves a user state snapshot."""
        user = self.app_context.state.users.get(username)
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
        existing = self.app_context.state.users.get(username)
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

        self.app_context.state.users.set(user)
        return user
