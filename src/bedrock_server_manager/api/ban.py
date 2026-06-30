import logging
from typing import Any, Dict, Optional

from ..context import AppContext
from ..db.models import Server, ServerBan
from ..error import UserInputError
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_app_event

logger = logging.getLogger(__name__)


@api_method("add_server_ban_api")
@trigger_app_event(before="before_add_server_ban", after="after_add_server_ban")
def add_server_ban_api(
    app_context: AppContext,
    server_name: str,
    player_name: str,
    xuid: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Adds a player to the server ban list."""
    if not server_name or not player_name or not xuid:
        raise UserInputError("server_name, player_name, and xuid are required.")

    if app_context.settings.db is None:
        return {"status": "error", "message": "Database is not initialized."}

    logger.info(
        f"API: Adding ban for player '{player_name}' ({xuid}) on server '{server_name}'."
    )

    with app_context.settings.db.session_manager() as db:
        server = db.query(Server).filter(Server.server_name == server_name).first()
        if not server:
            return {
                "status": "error",
                "message": f"Server '{server_name}' not found in database.",
            }

        # Check if already banned
        existing_ban = (
            db.query(ServerBan)
            .filter(ServerBan.server_id == server.id, ServerBan.xuid == xuid)
            .first()
        )

        if existing_ban:
            existing_ban.reason = reason
            db.commit()
            return {
                "status": "success",
                "message": f"Ban updated for player '{player_name}'.",
            }

        new_ban = ServerBan(
            server_id=server.id, player_name=player_name, xuid=xuid, reason=reason
        )
        db.add(new_ban)
        db.commit()
        return {
            "status": "success",
            "message": f"Player '{player_name}' banned successfully.",
        }


@trigger_app_event(before="before_remove_server_ban", after="after_remove_server_ban")
def remove_server_ban_api(
    app_context: AppContext, server_name: str, xuid: str
) -> Dict[str, Any]:
    """Removes a player from the server ban list."""
    if not server_name or not xuid:
        raise UserInputError("server_name and xuid are required.")

    if app_context.settings.db is None:
        return {"status": "error", "message": "Database is not initialized."}

    logger.info(f"API: Removing ban for XUID '{xuid}' on server '{server_name}'.")

    with app_context.settings.db.session_manager() as db:
        server = db.query(Server).filter(Server.server_name == server_name).first()
        if not server:
            return {
                "status": "error",
                "message": f"Server '{server_name}' not found in database.",
            }

        ban = (
            db.query(ServerBan)
            .filter(ServerBan.server_id == server.id, ServerBan.xuid == xuid)
            .first()
        )

        if not ban:
            return {
                "status": "error",
                "message": f"Ban not found for XUID '{xuid}' on server '{server_name}'.",
            }

        db.delete(ban)
        db.commit()
        return {"status": "success", "message": f"Ban removed successfully."}


@api_method("get_server_bans_api")
def get_server_bans_api(app_context: AppContext, server_name: str) -> Dict[str, Any]:
    """Retrieves all bans for a specific server."""
    if not server_name:
        raise UserInputError("server_name is required.")

    if app_context.settings.db is None:
        return {"status": "error", "message": "Database is not initialized."}

    with app_context.settings.db.session_manager() as db:
        server = db.query(Server).filter(Server.server_name == server_name).first()
        if not server:
            return {
                "status": "error",
                "message": f"Server '{server_name}' not found in database.",
            }

        bans = db.query(ServerBan).filter(ServerBan.server_id == server.id).all()
        ban_list = [
            {
                "player_name": ban.player_name,
                "xuid": ban.xuid,
                "reason": ban.reason,
                "banned_at": ban.banned_at.isoformat() if ban.banned_at else None,
            }
            for ban in bans
        ]

        return {"status": "success", "bans": ban_list}
