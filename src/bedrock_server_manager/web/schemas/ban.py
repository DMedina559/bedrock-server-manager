from typing import Optional

from pydantic import BaseModel


class BanAddRequest(BaseModel):
    player_name: str
    xuid: str
    reason: Optional[str] = None


class BanRemoveRequest(BaseModel):
    xuid: str
