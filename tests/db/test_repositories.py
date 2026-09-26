"""
Tests for domain repository classes and Storage coordination.
"""

from bedrock_server_manager.db.storage import Storage
from bedrock_server_manager.state.models import (
    PluginInfoState,
    ServerConfigState,
    UserInfoState,
)


async def test_settings_repository(db):
    storage = Storage(db)
    async with storage.transaction() as session:
        await storage.settings_repo.save_settings(
            session, {"web.port": 8080, "server.name": "test"}
        )

    async with storage.transaction() as session:
        all_settings = await storage.settings_repo.get_all_settings(session)
        assert all_settings["web.port"] == 8080
        assert all_settings["server.name"] == "test"


async def test_server_repository(db):
    storage = Storage(db)
    cfg = ServerConfigState(
        server_name="test_srv",
        installed_version="1.20.0",
        status="RUNNING",
        autostart=True,
    )
    async with storage.transaction() as session:
        await storage.server_repo.save_server(session, cfg)

    async with storage.transaction() as session:
        servers = await storage.server_repo.get_all_servers(session)
        assert len(servers) == 1
        assert servers[0].server_name == "test_srv"
        assert servers[0].autostart is True


async def test_plugin_repository(db):
    storage = Storage(db)
    plugin = PluginInfoState(
        plugin_name="test_plugin",
        enabled=True,
        version="1.0.0",
        author="Dev",
    )
    async with storage.transaction() as session:
        await storage.plugin_repo.save_plugin(session, plugin)

    async with storage.transaction() as session:
        plugins = await storage.plugin_repo.get_all_plugins(session)
        assert len(plugins) == 1
        assert plugins[0].plugin_name == "test_plugin"
        assert plugins[0].enabled is True


async def test_user_repository(db):
    storage = Storage(db)
    user = UserInfoState(
        username="admin_user",
        role="admin",
        theme="dark",
        is_active=True,
    )
    async with storage.transaction() as session:
        await storage.user_repo.save_user(session, user)

    async with storage.transaction() as session:
        users = await storage.user_repo.get_all_users(session)
        assert len(users) == 1
        assert users[0].username == "admin_user"
        assert users[0].role == "admin"


async def test_server_ban_repository(db):
    storage = Storage(db)

    # First add a server
    cfg = ServerConfigState(server_name="banned_srv")
    async with storage.transaction() as session:
        await storage.server_repo.save_server(session, cfg)

    # Add ban
    async with storage.transaction() as session:
        res = await storage.ban_repo.add_or_update_ban(
            session, "banned_srv", "Gamer123", "xuid_123", "Griefing"
        )
        assert res.success is True

    # Get bans
    async with storage.transaction() as session:
        bans = await storage.ban_repo.get_bans(session, "banned_srv")
        assert bans.success is True
        assert len(bans.bans) == 1
        assert bans.bans[0].xuid == "xuid_123"

    # Remove ban
    async with storage.transaction() as session:
        rem_res = await storage.ban_repo.remove_ban(session, "banned_srv", "xuid_123")
        assert rem_res.success is True

    # Verify no bans
    async with storage.transaction() as session:
        bans = await storage.ban_repo.get_bans(session, "banned_srv")
        assert len(bans.bans) == 0
