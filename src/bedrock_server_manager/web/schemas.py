from typing import Optional, Any, List, Dict
from pydantic import BaseModel


class ActionResponse(BaseModel):
    status: str = "success"
    message: str
    details: Optional[Any] = None


class BaseApiResponse(BaseModel):
    status: str
    message: Optional[str] = None
