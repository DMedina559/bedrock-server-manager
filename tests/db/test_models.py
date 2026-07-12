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


def test_user_model(db_session):
    """Test User model creation, read, update, delete."""
    user = User(username="testuser", hashed_password="hashed_pw", role="admin")
    db_session.add(user)
    db_session.commit()

    # Read
    fetched_user = db_session.query(User).filter_by(username="testuser").first()
    assert fetched_user is not None
    assert fetched_user.role == "admin"
    assert fetched_user.theme == "default"
    assert fetched_user.is_active is True

    # Update
    fetched_user.full_name = "Test User"
    db_session.commit()

    updated_user = db_session.query(User).filter_by(username="testuser").first()
    assert updated_user.full_name == "Test User"

    # Delete
    db_session.delete(updated_user)
    db_session.commit()

    deleted_user = db_session.query(User).filter_by(username="testuser").first()
    assert deleted_user is None


def test_setting_model(db_session):
    """Test Setting model CRUD."""
    setting = Setting(key="test.key", value={"key": "val"})
    db_session.add(setting)
    db_session.commit()

    fetched = db_session.query(Setting).filter_by(key="test.key").first()
    assert fetched.value == {"key": "val"}

    db_session.delete(fetched)
    db_session.commit()


def test_server_and_ban_relationship(db_session):
    """Test Server and ServerBan models and their relationship."""
    server = Server(server_name="main_server", installed_version="1.20.0")
    db_session.add(server)
    db_session.commit()

    # Create Ban
    ban = ServerBan(
        server_id=server.id,
        player_name="bad_player",
        xuid="123456789",
        reason="cheating",
    )
    db_session.add(ban)
    db_session.commit()

    # Test relationship from server -> bans
    fetched_server = (
        db_session.query(Server).filter_by(server_name="main_server").first()
    )
    assert len(fetched_server.bans) == 1
    assert fetched_server.bans[0].player_name == "bad_player"

    # Test relationship from ban -> server
    fetched_ban = (
        db_session.query(ServerBan).filter_by(player_name="bad_player").first()
    )
    assert fetched_ban.server.server_name == "main_server"

    # Cleanup
    db_session.delete(fetched_ban)
    db_session.delete(fetched_server)
    db_session.commit()


def test_plugin_model(db_session):
    """Test Plugin model CRUD."""
    plugin = Plugin(plugin_name="cool_plugin", enabled=True, version="1.0.0")
    db_session.add(plugin)
    db_session.commit()

    fetched = db_session.query(Plugin).filter_by(plugin_name="cool_plugin").first()
    assert fetched.enabled is True

    db_session.delete(fetched)
    db_session.commit()


def test_registration_token_model(db_session):
    """Test RegistrationToken model CRUD."""
    token = RegistrationToken(token="abc-123", role="user", expires=1234567890)
    db_session.add(token)
    db_session.commit()

    fetched = db_session.query(RegistrationToken).filter_by(token="abc-123").first()
    assert fetched.role == "user"

    db_session.delete(fetched)
    db_session.commit()


def test_player_model(db_session):
    """Test Player model CRUD."""
    player = Player(player_name="steve", xuid="987654321")
    db_session.add(player)
    db_session.commit()

    fetched = db_session.query(Player).filter_by(player_name="steve").first()
    assert fetched.xuid == "987654321"

    db_session.delete(fetched)
    db_session.commit()


def test_audit_log_relationship(db_session):
    """Test AuditLog and its relationship with User."""
    user = User(username="audit_user", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    log = AuditLog(
        user_id=user.id, action="test_action", details={"info": "started test"}
    )
    db_session.add(log)
    db_session.commit()

    fetched_log = db_session.query(AuditLog).filter_by(action="test_action").first()
    assert fetched_log.user.username == "audit_user"
    assert fetched_log.details["info"] == "started test"

    db_session.delete(fetched_log)
    db_session.delete(user)
    db_session.commit()
