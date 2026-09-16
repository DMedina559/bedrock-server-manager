import pytest

from bedrock_server_manager.api.ban import (
    add_server_ban_api,
    get_server_bans_api,
    remove_server_ban_api,
)
from bedrock_server_manager.db.models import Server, ServerBan
from bedrock_server_manager.error import UserInputError


async def test_add_server_ban_api_success(app_context, db_session):
    """Test add_server_ban_api successfully adds a ban to the database."""
    # Insert mock server into the same DB the app_context uses
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    db_session.commit()

    result = await add_server_ban_api(
        app_context, "test_server", "bad_player", "xuid123", "griefing"
    )

    assert (
        result["status"] == "success"
    ), f"API returned an error: {result.get('message')}"
    assert "banned successfully" in result["message"]

    # Verify in DB
    ban = db_session.query(ServerBan).filter_by(xuid="xuid123").first()
    assert ban is not None
    assert ban.player_name == "bad_player"
    assert ban.reason == "griefing"


async def test_add_server_ban_api_update(app_context, db_session):
    """Test add_server_ban_api updates an existing ban instead of duplicating."""
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    db_session.commit()

    # First ban
    await add_server_ban_api(
        app_context, "test_server", "bad_player", "xuid123", "old reason"
    )
    # Update ban
    result = await add_server_ban_api(
        app_context, "test_server", "bad_player", "xuid123", "new reason"
    )

    assert (
        result["status"] == "success"
    ), f"API returned an error: {result.get('message')}"
    assert "Ban updated" in result["message"]

    ban = db_session.query(ServerBan).filter_by(xuid="xuid123").first()
    assert ban.reason == "new reason"


async def test_add_server_ban_api_missing_args(app_context):
    """Test add_server_ban_api rejects missing core arguments."""
    with pytest.raises(UserInputError):
        await add_server_ban_api(app_context, "", "", "")


async def test_add_server_ban_api_server_missing(app_context):
    """Test add_server_ban_api handles valid args against a non-existent database server smoothly."""
    result = await add_server_ban_api(app_context, "ghost_server", "banned", "xuid")
    assert result["status"] == "error"
    assert "not found in database" in result["message"]


async def test_add_server_ban_api_no_db(app_context):
    """Test add_server_ban_api cleanly fails if DB is somehow uninitialized."""
    app_context.settings.db = None
    result = await add_server_ban_api(app_context, "test_server", "banned", "xuid")
    assert result["status"] == "error"
    assert "Database is not initialized" in result["message"]


async def test_remove_server_ban_api_success(app_context, db_session):
    """Test remove_server_ban_api drops the ban record successfully."""
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    db_session.commit()

    await add_server_ban_api(app_context, "test_server", "bad_player", "xuid123")

    result = await remove_server_ban_api(app_context, "test_server", "xuid123")
    assert (
        result["status"] == "success"
    ), f"API returned an error: {result.get('message')}"

    ban = db_session.query(ServerBan).filter_by(xuid="xuid123").first()
    assert ban is None


async def test_remove_server_ban_api_not_found(app_context, db_session):
    """Test remove_server_ban_api gracefully handles missing records."""
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    db_session.commit()

    result = await remove_server_ban_api(app_context, "test_server", "xuid_missing")
    assert result["status"] == "error"
    assert "not found" in result["message"]


async def test_remove_server_ban_api_missing_args(app_context):
    """Test remove_server_ban_api traps missing core arguments."""
    with pytest.raises(UserInputError):
        await remove_server_ban_api(app_context, "", "")


async def test_get_server_bans_api_success(app_context, db_session):
    """Test get_server_bans_api returns all bans for the server."""
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    db_session.commit()

    await add_server_ban_api(app_context, "test_server", "p1", "x1")
    await add_server_ban_api(app_context, "test_server", "p2", "x2")

    result = await get_server_bans_api(app_context, "test_server")
    assert (
        result["status"] == "success"
    ), f"API returned an error: {result.get('message')}"
    assert len(result["bans"]) == 2


async def test_get_server_bans_api_missing_args(app_context):
    """Test get_server_bans_api traps missing core arguments."""
    with pytest.raises(UserInputError):
        await get_server_bans_api(app_context, "")
