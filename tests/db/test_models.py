from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bedrock_server_manager.db.models import (
    AuditLog,
    Player,
    Plugin,
    RegistrationToken,
    Server,
    ServerBan,
    Setting,
    User,
)


async def test_user_model(db_session):
    """Test User model creation, read, update, delete."""
    user = User(username="testuser", hashed_password="hashed_pw", role="admin")
    db_session.add(user)
    await db_session.commit()

    # Read
    res = await db_session.execute(select(User).filter_by(username="testuser"))
    fetched_user = res.scalars().first()
    assert fetched_user is not None
    assert fetched_user.role == "admin"
    assert fetched_user.theme == "default"
    assert fetched_user.is_active is True

    # Update
    fetched_user.full_name = "Test User"
    await db_session.commit()

    res = await db_session.execute(select(User).filter_by(username="testuser"))
    updated_user = res.scalars().first()
    assert updated_user.full_name == "Test User"

    # Delete
    await db_session.delete(updated_user)
    await db_session.commit()

    res = await db_session.execute(select(User).filter_by(username="testuser"))
    deleted_user = res.scalars().first()
    assert deleted_user is None


async def test_setting_model(db_session):
    """Test Setting model CRUD."""
    setting = Setting(key="test.key", value={"key": "val"})
    db_session.add(setting)
    await db_session.commit()

    res = await db_session.execute(select(Setting).filter_by(key="test.key"))
    fetched = res.scalars().first()
    assert fetched.value == {"key": "val"}

    await db_session.delete(fetched)
    await db_session.commit()


async def test_server_and_ban_relationship(db_session):
    """Test Server and ServerBan models and their relationship."""
    server = Server(server_name="main_server", installed_version="1.20.0")
    db_session.add(server)
    await db_session.commit()

    # Create Ban
    ban = ServerBan(
        server_id=server.id,
        player_name="bad_player",
        xuid="123456789",
        reason="cheating",
    )
    db_session.add(ban)
    await db_session.commit()

    # Test relationship from server -> bans
    res = await db_session.execute(
        select(Server)
        .options(selectinload(Server.bans))
        .filter_by(server_name="main_server")
    )
    fetched_server = res.scalars().first()
    assert len(fetched_server.bans) == 1
    assert fetched_server.bans[0].player_name == "bad_player"

    # Test relationship from ban -> server
    res = await db_session.execute(
        select(ServerBan)
        .options(selectinload(ServerBan.server))
        .filter_by(player_name="bad_player")
    )
    fetched_ban = res.scalars().first()
    assert fetched_ban.server.server_name == "main_server"

    # Cleanup
    await db_session.delete(fetched_ban)
    await db_session.delete(fetched_server)
    await db_session.commit()


async def test_plugin_model(db_session):
    """Test Plugin model CRUD."""
    plugin = Plugin(plugin_name="cool_plugin", enabled=True, version="1.0.0")
    db_session.add(plugin)
    await db_session.commit()

    res = await db_session.execute(select(Plugin).filter_by(plugin_name="cool_plugin"))
    fetched = res.scalars().first()
    assert fetched.enabled is True

    await db_session.delete(fetched)
    await db_session.commit()


async def test_registration_token_model(db_session):
    """Test RegistrationToken model CRUD."""
    token = RegistrationToken(token="abc-123", role="user", expires=1234567890)
    db_session.add(token)
    await db_session.commit()

    res = await db_session.execute(select(RegistrationToken).filter_by(token="abc-123"))
    fetched = res.scalars().first()
    assert fetched.role == "user"

    await db_session.delete(fetched)
    await db_session.commit()


async def test_player_model(db_session):
    """Test Player model CRUD."""
    player = Player(player_name="steve", xuid="987654321")
    db_session.add(player)
    await db_session.commit()

    res = await db_session.execute(select(Player).filter_by(player_name="steve"))
    fetched = res.scalars().first()
    assert fetched.xuid == "987654321"

    await db_session.delete(fetched)
    await db_session.commit()


async def test_audit_log_relationship(db_session):
    """Test AuditLog and its relationship with User."""
    user = User(username="audit_user", hashed_password="pw")
    db_session.add(user)
    await db_session.commit()

    log = AuditLog(
        user_id=user.id, action="test_action", details={"info": "started test"}
    )
    db_session.add(log)
    await db_session.commit()

    res = await db_session.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .filter_by(action="test_action")
    )
    fetched_log = res.scalars().first()
    assert fetched_log.user.username == "audit_user"
    assert fetched_log.details["info"] == "started test"

    await db_session.delete(fetched_log)
    await db_session.delete(user)
    await db_session.commit()
