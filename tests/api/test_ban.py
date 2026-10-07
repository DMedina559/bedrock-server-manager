import pytest
from pydantic import ValidationError
from sqlalchemy import select

from bedrock_server_manager.api.ban import (
    add_server_ban,
    get_server_bans,
    remove_server_ban,
)
from bedrock_server_manager.api.models import (
    AddServerBanRequest,
    GetServerBansRequest,
    RemoveServerBanRequest,
)
from bedrock_server_manager.db.models import Server, ServerBan
from bedrock_server_manager.error import BSMError


async def test_add_server_ban_success(app_context, db_session):
    """Test add_server_ban successfully adds a ban to the database."""
    # Insert mock server into the same DB the app_context uses
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    await db_session.commit()

    result = (
        await add_server_ban(
            request=AddServerBanRequest(
                server_name="test_server",
                player_name="bad_player",
                xuid="xuid123",
                reason="griefing",
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert (
        result["status"] == "success"
    ), f"API returned an error: {result.get('message')}"
    assert "banned successfully" in result["message"]

    # Verify in DB
    db_session.expire_all()
    res = await db_session.execute(select(ServerBan).filter_by(xuid="xuid123"))
    ban = res.scalars().first()
    assert ban is not None
    assert ban.player_name == "bad_player"
    assert ban.reason == "griefing"


async def test_add_server_ban_update(app_context, db_session):
    """Test add_server_ban updates an existing ban instead of duplicating."""
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    await db_session.commit()

    # First ban
    (
        await add_server_ban(
            request=AddServerBanRequest(
                server_name="test_server",
                player_name="bad_player",
                xuid="xuid123",
                reason="old reason",
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")
    # Update ban
    result = (
        await add_server_ban(
            request=AddServerBanRequest(
                server_name="test_server",
                player_name="bad_player",
                xuid="xuid123",
                reason="new reason",
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert (
        result["status"] == "success"
    ), f"API returned an error: {result.get('message')}"
    assert "Ban updated" in result["message"]

    db_session.expire_all()
    res = await db_session.execute(select(ServerBan).filter_by(xuid="xuid123"))
    ban = res.scalars().first()
    assert ban.reason == "new reason"


async def test_add_server_ban_missing_args(app_context):
    """Test add_server_ban rejects missing core arguments."""
    with pytest.raises(ValidationError):
        (
            await add_server_ban(
                request=AddServerBanRequest(server_name="", player_name="", xuid=""),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_add_server_ban_server_missing(app_context):
    """Test add_server_ban handles valid args against a non-existent database server smoothly."""
    with pytest.raises(BSMError):
        (
            await add_server_ban(
                request=AddServerBanRequest(
                    server_name="ghost_server", player_name="banned", xuid="xuid"
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_add_server_ban_no_db(app_context):
    """Test add_server_ban cleanly fails if DB is somehow uninitialized."""
    app_context._storage = None
    app_context._server_service = None
    with pytest.raises(BSMError):
        (
            await add_server_ban(
                request=AddServerBanRequest(
                    server_name="test_server", player_name="banned", xuid="xuid"
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_remove_server_ban_success(app_context, db_session):
    """Test remove_server_ban drops the ban record successfully."""
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    await db_session.commit()

    (
        await add_server_ban(
            request=AddServerBanRequest(
                server_name="test_server", player_name="bad_player", xuid="xuid123"
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    result = (
        await remove_server_ban(
            request=RemoveServerBanRequest(server_name="test_server", xuid="xuid123"),
            app_context=app_context,
        )
    ).model_dump(mode="python")
    assert (
        result["status"] == "success"
    ), f"API returned an error: {result.get('message')}"

    db_session.expire_all()
    res = await db_session.execute(select(ServerBan).filter_by(xuid="xuid123"))
    ban = res.scalars().first()
    assert ban is None


async def test_remove_server_ban_not_found(app_context, db_session):
    """Test remove_server_ban gracefully handles missing records."""
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    await db_session.commit()

    with pytest.raises(BSMError):
        (
            await remove_server_ban(
                request=RemoveServerBanRequest(
                    server_name="test_server", xuid="xuid_missing"
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_remove_server_ban_missing_args(app_context):
    """Test remove_server_ban traps missing core arguments."""
    with pytest.raises(ValidationError):
        (
            await remove_server_ban(
                request=RemoveServerBanRequest(server_name="", xuid=""),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_get_server_bans_success(app_context, db_session):
    """Test get_server_bans returns all bans for the server."""
    server = Server(server_name="test_server", installed_version="1.0")
    db_session.add(server)
    await db_session.commit()

    (
        await add_server_ban(
            request=AddServerBanRequest(
                server_name="test_server", player_name="p1", xuid="x1"
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")
    (
        await add_server_ban(
            request=AddServerBanRequest(
                server_name="test_server", player_name="p2", xuid="x2"
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    result = (
        await get_server_bans(
            request=GetServerBansRequest(server_name="test_server"),
            app_context=app_context,
        )
    ).model_dump(mode="python")
    assert (
        result["status"] == "success"
    ), f"API returned an error: {result.get('message')}"
    assert len(result["bans"]) == 2


async def test_get_server_bans_missing_args(app_context):
    """Test get_server_bans traps missing core arguments."""
    with pytest.raises(ValidationError):
        (
            await get_server_bans(
                request=GetServerBansRequest(server_name=""), app_context=app_context
            )
        ).model_dump(mode="python")
