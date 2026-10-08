"""Runtime snapshots follow verified processes rather than independent caches."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.state.models import ServerRuntimeInfo


async def test_process_probe_updates_runtime_and_stopped_probe_clears_stats(
    real_bedrock_server, monkeypatch
):
    server = real_bedrock_server
    server._process = SimpleNamespace(pid=123, poll=lambda: None)
    assert await server.is_running()
    snapshot = server.state.runtime.get_server_runtime(server.server_name)
    assert snapshot.running and snapshot.pid == 123
    server._runtime_state.update_server_runtime(
        server.server_name, cpu_percent=20.0, memory_mb=100.0
    )
    server._process = None
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.process_mixin.system_base.is_server_running",
        AsyncMock(return_value=False),
    )
    assert not await server.is_running()
    snapshot = server.state.runtime.get_server_runtime(server.server_name)
    assert (
        snapshot.pid is None and snapshot.cpu_percent == 0 and snapshot.memory_mb == 0
    )


@pytest.mark.parametrize("values", [{"pid": 1}, {"players_online": 1}])
def test_runtime_rejects_inconsistent_snapshots(values):
    with pytest.raises(ValidationError):
        ServerRuntimeInfo.model_validate(values)
