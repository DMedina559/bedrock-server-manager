"""Lifecycle plugins coordinate using real backup outcomes and operation ancestry."""

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.backup_restore import backup_all
from bedrock_server_manager.api.install import update_server
from bedrock_server_manager.api.server import start_server, stop_server
from bedrock_server_manager.error import APICancelledError
from bedrock_server_manager.events import EventOptions
from bedrock_server_manager.operations import OperationResultQuery, OperationService


async def load_default(plugin_factory, name):
    path = (
        Path(__file__).parents[2]
        / "src/bedrock_server_manager/plugins/default"
        / f"{name}.py"
    )
    return await plugin_factory(name, path.read_text())


def backups(server):
    return list(Path(server.backups.server_backup_directory).glob("*.bsmbackup"))


@pytest.mark.parametrize("reuse,expected", [(True, 1), (False, 2)])
async def test_start_reuses_pre_update_backup(
    app_context, populated_server, plugin_factory, download_api, reuse, expected
):
    server = populated_server
    await server.set_version("1.20.1.1")
    await server.set_autoupdate(True)
    # Load backup first: execution order must come from priority, not discovery.
    plugin = await load_default(plugin_factory, "backup_on_start")
    await plugin.set_plugin_setting("reuse_sequence_backup", reuse)
    await load_default(plugin_factory, "update_before_start")
    seen = []

    async def inspect_sequence(**data):
        seen.extend(
            plugin.api.operations.results(OperationResultQuery(name="backup.create"))
        )
        context = plugin.api.events.current()
        assert context.name == "before_server_start"
        assert context.sequence_id == plugin.api.operations.current().sequence_id
        assert plugin.api.operations.current().name == "server.start"
        update = plugin.api.operations.results(
            OperationResultQuery(name="server.update")
        )[-1]
        assert update.outcome in {"updated", "up_to_date"}

    plugin.api.events.listen("before_server_start", inspect_sequence, priority=-100)
    result = await start_server(
        {"server_name": server.server_name}, app_context=app_context
    )
    assert result.outcome == "started"
    assert await server.get_version() == "1.26.45.1"
    assert len(backups(server)) == expected
    assert len(seen) == expected
    assert seen[0].purpose == "pre_update"
    assert len({item.sequence_id for item in seen}) == 1
    assert plugin.api.operations.current() is None
    assert plugin.api.operations.results() == ()
    assert plugin.api.events.current() is None
    # A subsequent independent start requires a new backup.
    await stop_server({"server_name": server.server_name}, app_context=app_context)
    await start_server({"server_name": server.server_name}, app_context=app_context)
    assert len(backups(server)) == expected + 1


async def test_running_start_does_not_dispatch_pre_start_work(
    app_context, populated_server, plugin_factory
):
    plugin = await load_default(plugin_factory, "backup_on_start")
    await populated_server.start()
    seen = []

    async def observe(**data):
        seen.append(data)

    plugin.api.events.listen("before_server_start", observe)
    result = await start_server(
        {"server_name": populated_server.server_name}, app_context=app_context
    )
    assert result.outcome == "already_running"
    assert not backups(populated_server)
    assert seen == []


async def test_explicit_update_restart_does_not_reenter_update(
    app_context, populated_server, plugin_factory, download_api
):
    server = populated_server
    await server.set_version("1.20.1.1")
    await server.set_autoupdate(True)
    await server.start()
    await load_default(plugin_factory, "backup_on_start")
    plugin = await load_default(plugin_factory, "update_before_start")
    updates, observed = [], []

    async def updating(**data):
        updates.append(plugin.api.operations.current())

    async def restarted(**data):
        observed.extend(
            plugin.api.operations.results(OperationResultQuery(name="backup.create"))
        )

    plugin.api.events.listen("before_server_update", updating)
    plugin.api.events.listen("before_server_start", restarted, priority=-100)
    result = await update_server(
        {"server_name": server.server_name, "send_message": False},
        app_context=app_context,
    )
    assert result.updated
    assert await server.is_running()
    assert len(updates) == len(observed) == len(backups(server)) == 1
    assert updates[0].sequence_id == observed[0].sequence_id


async def test_cancelled_backup_prevents_update(
    app_context, populated_server, plugin_factory, download_api
):
    await populated_server.set_version("1.20.1.1")
    plugin = await plugin_factory(
        "cancel_backup",
        "from bedrock_server_manager import PluginBase\nclass Cancel(PluginBase):\n    version = '1.0'\n",
    )

    async def cancel(**data):
        data["event"].cancel("Backup prohibited")

    plugin.api.events.listen("before_backup", cancel)
    with pytest.raises(APICancelledError):
        await update_server(
            {"server_name": populated_server.server_name}, app_context=app_context
        )
    assert await populated_server.get_version() == "1.20.1.1"
    assert not backups(populated_server)
    assert app_context.operations.current() is None


@pytest.mark.parametrize("kind", ["partial", "missing", "previous_sequence"])
async def test_ineligible_backup_does_not_suppress_start_backup(
    app_context, populated_server, plugin_factory, monkeypatch, kind
):
    server = populated_server
    plugin = await load_default(plugin_factory, "backup_on_start")
    await plugin.set_plugin_setting("backup_mode", "selected")
    if kind == "previous_sequence":
        await backup_all({"server_name": server.server_name}, app_context=app_context)
    else:

        async def earlier_backup(**data):
            if kind == "missing":
                path = Path(server.paths.server_dir) / "allowlist.json"
                contents = path.read_text()
                path.unlink()
                try:
                    await server.backups.backup_all_data()
                finally:
                    path.write_text(contents)
            else:

                def fail_copy(*args):
                    raise OSError("Injected filesystem failure")

                with monkeypatch.context() as fault:
                    fault.setattr(
                        "bedrock_server_manager.backups.server.copy_source", fail_copy
                    )
                    with pytest.raises(OSError):
                        await server.backups.backup_all_data()

        plugin.api.events.listen("before_server_start", earlier_backup, priority=50)
    await start_server({"server_name": server.server_name}, app_context=app_context)
    assert len(backups(server)) == (1 if kind == "partial" else 2)


async def test_failed_backup_and_listener_failure_have_distinct_outcomes(
    app_context, populated_server, plugin_factory, monkeypatch
):
    service = app_context.operations
    server = populated_server
    plugin = await load_default(plugin_factory, "backup_on_start")

    def fail_world(*args):
        raise OSError("Injected world read failure")

    with service.scope("example"):
        with monkeypatch.context() as fault:
            fault.setattr(
                "bedrock_server_manager.backups.server.copy_source", fail_world
            )
            with pytest.raises(OSError):
                await server.backups.backup_all_data()
        assert service.results()[0].status == "failed"
        assert service.results()[0].outcome == "failed"
        await server.backups.backup_all_data()

        async def fail_listener(**data):
            raise RuntimeError("Notification failure")

        plugin.api.events.listen("after_backup", fail_listener)
        await backup_all({"server_name": server.server_name}, app_context=app_context)
        assert (
            service.results(OperationResultQuery(name="backup.create"))[-1].outcome
            == "completed"
        )
        # The successful backups satisfy the next start despite the listener failure.
        count = len(backups(server))
        await start_server({"server_name": server.server_name}, app_context=app_context)
        assert len(backups(server)) == count


async def test_scope_bounds_immutability_failure_and_child_task_isolation():
    service = OperationService(history_limit=1)
    with service.scope("root") as root:
        with service.scope("first"):
            pass
        with pytest.raises(ValueError):
            with service.scope("second"):
                raise ValueError("failure")
        assert service.sequence().results_truncated
        assert service.results()[0].status == "failed"
        with pytest.raises(ValidationError):
            service.current().name = "changed"

        async def independent():
            assert service.current() is None
            with service.scope("child_task") as child:
                assert child.snapshot.sequence_id != root.snapshot.sequence_id

        await asyncio.create_task(independent())
        assert service.current().operation_id == root.snapshot.operation_id
    assert service.current() is None
    assert service.results() == ()
    with service.scope("new"):
        assert service.results() == ()


async def test_operation_results_survive_disabled_event_history():
    from bedrock_server_manager.events import EventBus
    from bedrock_server_manager.plugins.api_bridge import create_app_api

    bus = EventBus(EventOptions(history_limit=0))
    api = create_app_api("application", None, is_core=True, events=bus)
    with bus.operations.scope("root"):
        with bus.operations.scope("backup.create") as backup:
            backup.finish("completed", scope=("world",))
        await bus.emit("example")
        assert bus.diagnostics().recent == []
        assert api.operations.results()[0].outcome == "completed"
    await bus.close()


async def test_unloaded_plugin_cannot_read_operations(app_context, plugin_factory):
    plugin = await plugin_factory(
        "owned",
        "from bedrock_server_manager import PluginBase\nclass Owned(PluginBase):\n    version = '1.0'\n",
    )
    capability = plugin.api.operations
    app_context.events.remove_owner("plugin:owned")
    for read in (
        capability.current,
        capability.sequence,
        capability.results,
        plugin.api.events.current,
    ):
        with pytest.raises(RuntimeError):
            read()


async def test_other_server_backup_does_not_satisfy_start(
    app_context,
    populated_server,
    plugin_factory,
    dummy_server_zip,
    valid_mcworld_zip,
    tmp_path,
):
    from bedrock_server_manager.api.install import install_new_server

    archive = dummy_server_zip(target_dir=tmp_path)
    await install_new_server(
        {
            "server_name": "other",
            "target_version": "CUSTOM",
            "server_zip_path": str(archive),
        },
        app_context=app_context,
    )
    other = app_context.get_server("other")
    await other.worlds.extract_mcworld(
        str(valid_mcworld_zip), await other.get_world_name()
    )
    await load_default(plugin_factory, "backup_on_start")
    with app_context.operations.scope("batch"):
        await other.backups.backup_all_data()
        await start_server(
            {"server_name": populated_server.server_name}, app_context=app_context
        )
        assert len(backups(populated_server)) == 1
        assert len(backups(other)) == 1


async def test_managed_task_and_sync_callback_context(
    app_context, populated_server, plugin_factory, wait_for_task
):
    plugin = await load_default(plugin_factory, "backup_on_start")
    service = app_context.operations
    seen = []

    def inspect_sync(**data):
        event = plugin.api.events.current()
        operation = plugin.api.operations.current()
        assert event.operation_id == operation.operation_id
        seen.append(event)

    async def background():
        assert plugin.api.events.current() is None
        assert plugin.api.operations.current() is None
        with service.scope("background") as operation:
            seen.append(operation.snapshot)

    async def submit(**data):
        task_id = await plugin.api.runtime.run_task(background)
        await wait_for_task(app_context, task_id)

    plugin.api.events.listen("before_server_start", inspect_sync, priority=50)
    plugin.api.events.listen("before_server_start", submit, priority=25)
    await start_server(
        {"server_name": populated_server.server_name}, app_context=app_context
    )
    assert seen[0].sequence_id != seen[1].sequence_id


async def test_active_results_capacity_concurrency_and_cancellation():
    from bedrock_server_manager.error import OperationConflictError

    service = OperationService(max_sequences=1)
    with service.scope("root") as root:
        with service.scope("backup.create") as active:
            active.finish("completed", scope=("world",))
            assert service.results() == ()

        async def capacity():
            with pytest.raises(OperationConflictError):
                with service.scope("independent"):
                    pass

        await asyncio.create_task(capacity())
        assert service.results()[0].parent_operation_id == root.snapshot.operation_id

    entered = asyncio.Event()
    handles = []

    async def cancelled():
        with service.scope("cancelled") as operation:
            handles.append(operation)
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(cancelled())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert handles[0].snapshot.status == "cancelled"
    with service.scope("after_cancellation"):
        assert service.results() == ()

    isolated = OperationService()
    barrier = asyncio.Event()
    ids = []

    async def concurrent(name):
        with isolated.scope(name) as operation:
            ids.append(operation.snapshot.sequence_id)
            if len(ids) == 2:
                barrier.set()
            await barrier.wait()
            with isolated.scope("nested") as nested:
                nested.finish(name)
            assert [item.outcome for item in isolated.results()] == [name]

    await asyncio.gather(concurrent("one"), concurrent("two"))
    assert len(set(ids)) == 2


async def test_complete_snapshot_with_absent_components_is_reused(
    app_context, populated_server, plugin_factory
):
    server = populated_server
    for name in ("allowlist.json", "permissions.json"):
        (Path(server.paths.server_dir) / name).unlink(missing_ok=True)
    await load_default(plugin_factory, "backup_on_start")
    with app_context.operations.scope("batch"):
        await backup_all({"server_name": server.server_name}, app_context=app_context)
        await start_server({"server_name": server.server_name}, app_context=app_context)
    assert len(backups(server)) == 1


async def test_legacy_component_scope_does_not_claim_script_configuration_coverage(
    app_context, populated_server, plugin_factory
):
    server = populated_server
    config = Path(server.paths.server_dir) / "config"
    config.mkdir(exist_ok=True)
    (config / "secrets.json").write_text('{"secret":"preserve"}')
    plugin = await load_default(plugin_factory, "backup_on_start")
    await plugin.set_plugin_setting("backup_mode", "selected")
    with app_context.operations.scope("batch"):
        with app_context.operations.scope(
            "backup.create", server_name=server.server_name
        ) as operation:
            operation.finish(
                "completed",
                scope=(
                    "world",
                    "server.properties",
                    "allowlist.json",
                    "permissions.json",
                    "bsm_settings",
                ),
            )
        await start_server({"server_name": server.server_name}, app_context=app_context)
    assert len(backups(server)) == 1
    inspected = await server.backups.inspect_snapshot(backups(server)[0].name)
    assert inspected.manifest.components["script_config"] == "included"


async def test_deleted_sequence_snapshot_is_not_reusable(app_context, populated_server):
    with app_context.operations.scope("batch"):
        snapshot = await populated_server.backups.create_snapshot()
        assert await populated_server.backups.can_reuse_sequence_snapshot()
        populated_server.backups.resolve_backup(snapshot.backup_id).unlink()
        assert not await populated_server.backups.can_reuse_sequence_snapshot()
