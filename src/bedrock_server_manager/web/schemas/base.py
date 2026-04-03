from typing import Any, Optional

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
    redirect_url: Optional[str] = None
    backups: Optional[Any] = None


class BaseApiResponse(BaseModel):
    """
    Base model for simple API responses.

    Attributes:
        status (str): The status of the operation.
        message (Optional[str]): An optional message.
    """

    status: str
    message: Optional[str] = None
