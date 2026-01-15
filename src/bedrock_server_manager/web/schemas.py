"""
Pydantic schemas for web API responses and data structures.

This module defines the Pydantic models used for data validation and serialization
in the web API layer.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ActionResponse(BaseModel):
    """
    Standard response model for API actions.

    Attributes:
        status (str): The status of the operation (e.g., "success", "error"). Defaults to "success".
        message (str): A human-readable message describing the result.
        details (Optional[Any]): Additional data or details related to the response.
        task_id (Optional[str]): The ID of a background task, if one was initiated.
    """

    status: str = "success"
    message: str
    details: Optional[Any] = None
    task_id: Optional[str] = None


class BaseApiResponse(BaseModel):
    """
    Base model for simple API responses.

    Attributes:
        status (str): The status of the operation.
        message (Optional[str]): An optional message.
    """

    status: str
    message: Optional[str] = None


class User(BaseModel):
    """
    Pydantic model representing a user.

    Attributes:
        id (int): The user's ID.
        username (str): The user's username.
        identity_type (str): The type of identity (e.g., "local").
        role (str): The user's role.
        is_active (bool): Whether the user is active.
        theme (str): The user's preferred theme. Defaults to "default".
    """

    id: int
    username: str
    identity_type: str
    role: str
    is_active: bool
    theme: str = "default"
