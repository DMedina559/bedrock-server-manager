from typing import Optional

from ...api.models.common import APIRequest


class BanAddRequest(APIRequest):
    player_name: str
    xuid: str
    reason: Optional[str] = None


class BanRemoveRequest(APIRequest):
    xuid: str
