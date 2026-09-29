from sqlalchemy import select

from bedrock_server_manager.db.models import Server
from bedrock_server_manager.state.app_state import AppState
from bedrock_server_manager.state.changeset import ChangeSet
from bedrock_server_manager.state.models import ServerConfigState


async def test_changeset_apply_to_storage(db, storage):
    state = AppState()
    await storage.load_state(state)

    # Prepare server in state
    cfg = ServerConfigState(
        server_name="changeset_server",
        installed_version="1.20",
        status="STOPPED",
        autostart=True,
    )
    state.servers.set(cfg)

    # Record change in ChangeSet
    cs = ChangeSet()
    cs.add_server("changeset_server")

    assert not cs.is_empty()

    # Apply changeset
    await storage.apply_changeset(state, cs)

    # Verify DB persistence
    async with db.session_manager() as session:
        res = await session.execute(
            select(Server).filter_by(server_name="changeset_server")
        )
        rec = res.scalars().first()
        assert rec is not None
        assert rec.autostart is True
