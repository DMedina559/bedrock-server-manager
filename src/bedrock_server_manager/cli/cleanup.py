# bedrock_server_manager/cli/cleanup.py
"""Define the ``bsm cleanup`` command for removing generated and orphaned application data."""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Set

import click

from ..context import AppContext
from ..contracts import CleanupResult, FailureInfo
from ..error import FileOperationError
from ..failures import classify_failure
from ..plugins.files import RESERVED_PLUGIN_NAMES
from .logs import (
    _discover_all_server_names,
    _is_cli_own_log,
    get_verified_server_processes,
    get_verified_web_process,
    resolve_active_app_log,
    resolve_server_logs,
)

logger = logging.getLogger(__name__)


# --- Core Cleanup Functions ---


def _cleanup_pycache(dry_run: bool = False) -> CleanupResult:
    """Clean this package's bytecode caches, reporting individual failures."""
    package_root = Path(__file__).resolve().parents[1]
    deleted = []
    failures = {}
    try:
        paths = list(package_root.rglob("__pycache__"))
    except OSError as error:
        raise FileOperationError("Cannot scan package caches.") from error
    for directory in paths:
        try:
            if directory.is_dir():
                if not dry_run:
                    shutil.rmtree(directory)
                deleted.append(str(directory))
        except OSError as error:
            failures[str(directory)] = classify_failure(error).error
    return CleanupResult(deleted=deleted, failures=failures)


def _prune_file_group(
    paths: list[Path],
    deleted: list[str],
    retained: list[str],
    failures: dict[str, FailureInfo],
    dry_run: bool = False,
    protected: Optional[Set[Path]] = None,
) -> None:
    """Delete all but the most recent file (and any ``protected`` files) in ``paths``."""
    if not paths:
        return
    protected_resolved = {p.resolve() for p in (protected or set())}
    ordered = sorted(paths, key=os.path.getmtime)
    keep_set = {ordered[-1].resolve()} | protected_resolved
    for path in ordered:
        resolved = path.resolve()
        if resolved in keep_set:
            retained.append(str(path))
            continue
        try:
            if not dry_run:
                path.unlink()
            deleted.append(str(path))
        except OSError as error:
            failures[str(path)] = classify_failure(error).error


def _cleanup_log_files(
    log_dir_path: Path,
    dry_run: bool = False,
    app_context: Optional[AppContext] = None,
) -> CleanupResult:
    """Clean rotated and historical application and server log files while preserving verified active logs."""
    if not log_dir_path.is_dir():
        raise FileOperationError("Log directory does not exist.")
    deleted: list[str] = []
    retained: list[str] = []
    failures: dict[str, FailureInfo] = {}

    web_proc = None
    server_procs: dict[str, object] = {}
    if app_context is not None:
        try:
            web_proc = asyncio.run(get_verified_web_process(app_context))
            all_servers = _discover_all_server_names(app_context, log_dir_path)
            server_procs = dict(
                asyncio.run(get_verified_server_processes(app_context, all_servers))
            )
        except Exception:
            pass

    _, active_web_log, _ = resolve_active_app_log(log_dir_path, web_proc)  # type: ignore[arg-type]
    protected_app: Set[Path] = {active_web_log} if active_web_log is not None else set()

    try:
        rotated_paths = list(log_dir_path.glob("*.log.*"))
        # Exclude the current short-lived CLI process's own open log file so it
        # never displaces the background web server's log as the retained file.
        app_logs = [
            p
            for p in log_dir_path.glob("bedrock_server_manager_*.log")
            if not _is_cli_own_log(p, log_dir_path)
        ]
    except OSError as error:
        raise FileOperationError("Cannot scan rotated logs.") from error

    _prune_file_group(
        rotated_paths,
        deleted,
        retained,
        failures,
        dry_run=dry_run,
        protected=protected_app,
    )
    _prune_file_group(
        app_logs,
        deleted,
        retained,
        failures,
        dry_run=dry_run,
        protected=protected_app,
    )

    servers_log_dir = log_dir_path / "servers"
    if servers_log_dir.is_dir():
        try:
            server_dirs = [p for p in servers_log_dir.iterdir() if p.is_dir()]
        except OSError as error:
            raise FileOperationError("Cannot scan server logs.") from error
        for s_dir in server_dirs:
            s_proc = server_procs.get(s_dir.name)
            _, active_s_log, _ = resolve_server_logs(
                log_dir_path, s_dir.name, s_proc  # type: ignore[arg-type]
            )
            protected_srv: Set[Path] = (
                {active_s_log} if active_s_log is not None else set()
            )
            try:
                s_rotated = list(s_dir.glob("*.log.*"))
                s_logs = list(s_dir.glob(f"{s_dir.name}_*.log"))
            except OSError as error:
                failures[str(s_dir)] = classify_failure(error).error
                continue
            _prune_file_group(
                s_rotated,
                deleted,
                retained,
                failures,
                dry_run=dry_run,
                protected=protected_srv,
            )
            _prune_file_group(
                s_logs,
                deleted,
                retained,
                failures,
                dry_run=dry_run,
                protected=protected_srv,
            )

    return CleanupResult(deleted=deleted, retained=retained, failures=failures)


def _discover_installed_plugin_names(app_context: AppContext) -> Set[str]:
    """Return all plugin names currently present on disk in user and default plugin dirs."""
    names: Set[str] = set()
    dirs: list[Path] = []
    user_dir = app_context.settings.get("paths.plugins")
    if user_dir:
        dirs.append(Path(str(user_dir)))
    default_dir = Path(__file__).resolve().parents[1] / "plugins" / "default"
    dirs.append(default_dir)

    for directory in dirs:
        if not directory.is_dir():
            continue
        try:
            for entry in directory.iterdir():
                if entry.name.startswith(("_", ".")):
                    continue
                if entry.is_file() and entry.suffix == ".py":
                    stem = entry.stem
                    if stem.lower() not in RESERVED_PLUGIN_NAMES:
                        names.add(stem)
                elif entry.is_dir() and (entry / "__init__.py").is_file():
                    if entry.name.lower() not in RESERVED_PLUGIN_NAMES:
                        names.add(entry.name)
        except OSError:
            continue
    return names


async def _cleanup_orphaned_plugins_async(
    app_context: AppContext, dry_run: bool = False
) -> CleanupResult:
    """Clean DB records, custom settings, and private directories for removed plugins."""
    installed = _discover_installed_plugin_names(app_context)
    deleted: list[str] = []
    retained: list[str] = sorted(installed)
    failures: dict[str, FailureInfo] = {}

    db_plugins: Set[str] = set(app_context.state.plugins.plugins.keys())
    db_plugin_settings: Set[str] = set(
        app_context.state.settings.plugin_settings.keys()
    )
    global_custom_plugins: Set[str] = set(app_context.state.settings.custom.keys())
    server_custom_plugins: Set[str] = set()
    for s_cfg in app_context.state.servers.servers.values():
        if isinstance(s_cfg.custom, dict):
            server_custom_plugins.update(s_cfg.custom.keys())

    orphaned_db_names = sorted(
        (
            db_plugins
            | db_plugin_settings
            | global_custom_plugins
            | server_custom_plugins
        )
        - installed
    )

    if orphaned_db_names:
        if dry_run:
            for name in orphaned_db_names:
                deleted.append(f"db:plugin:{name}")
        else:
            try:
                async with app_context.storage.write_lock:
                    async with app_context.storage.transaction() as session:
                        for name in orphaned_db_names:
                            await app_context.storage.plugin_repo.delete_plugin(
                                session, name
                            )
                            app_context.state.plugins.remove(name)
                            app_context.state.plugins.remove_dirty_plugin(name)

                        plugin_settings = dict(
                            app_context.state.settings.plugin_settings
                        )
                        custom_settings = dict(app_context.state.settings.custom)
                        settings_changed = False
                        for name in orphaned_db_names:
                            if name in plugin_settings:
                                plugin_settings.pop(name, None)
                                settings_changed = True
                            if name in custom_settings:
                                custom_settings.pop(name, None)
                                settings_changed = True
                        if settings_changed:
                            app_context.state.settings.set(
                                "plugin_settings", plugin_settings
                            )
                            app_context.state.settings.set("custom", custom_settings)
                            await app_context.storage.settings_repo.save_settings(
                                session, app_context.state.settings.to_dict()
                            )
                            app_context.state.settings.clear_dirty()

                        for s_name, s_cfg in list(
                            app_context.state.servers.servers.items()
                        ):
                            if isinstance(s_cfg.custom, dict) and any(
                                k in s_cfg.custom for k in orphaned_db_names
                            ):
                                new_custom = {
                                    k: v
                                    for k, v in s_cfg.custom.items()
                                    if k not in orphaned_db_names
                                }
                                updated = s_cfg.model_copy(
                                    update={"custom": new_custom}
                                )
                                await app_context.storage.server_repo.save_server(
                                    session, updated
                                )
                                app_context.state.servers.set(updated)
                                app_context.state.servers.remove_dirty_server(s_name)

                for name in orphaned_db_names:
                    deleted.append(f"db:plugin:{name}")
            except Exception as error:
                failures["db:plugins"] = classify_failure(error).error

    plugins_data_root = Path(app_context.config_dir) / "plugins"
    if plugins_data_root.is_dir():
        try:
            for sub in sorted(plugins_data_root.iterdir()):
                if not sub.is_dir():
                    continue
                if sub.name.lower() in RESERVED_PLUGIN_NAMES:
                    continue
                if sub.name not in installed:
                    try:
                        if not dry_run:
                            shutil.rmtree(sub)
                        deleted.append(str(sub))
                    except OSError as error:
                        failures[str(sub)] = classify_failure(error).error
        except OSError as error:
            failures[str(plugins_data_root)] = classify_failure(error).error

    return CleanupResult(deleted=deleted, retained=retained, failures=failures)


async def _cleanup_orphaned_servers_async(
    app_context: AppContext, dry_run: bool = False
) -> CleanupResult:
    """Clean DB records, runtime directories, and log directories for removed servers."""
    servers_dir_val = app_context.settings.get("paths.servers")
    installed_servers: Set[str] = set()
    if servers_dir_val and os.path.isdir(str(servers_dir_val)):
        try:
            for entry in Path(str(servers_dir_val)).iterdir():
                if entry.is_dir():
                    installed_servers.add(entry.name)
        except OSError:
            pass

    deleted: list[str] = []
    retained: list[str] = sorted(installed_servers)
    failures: dict[str, FailureInfo] = {}

    orphaned_db_servers = sorted(
        set(app_context.state.servers.servers.keys()) - installed_servers
    )
    if orphaned_db_servers:
        if dry_run:
            for s_name in orphaned_db_servers:
                deleted.append(f"db:server:{s_name}")
        else:
            try:
                async with app_context.storage.write_lock:
                    async with app_context.storage.transaction() as session:
                        for s_name in orphaned_db_servers:
                            await app_context.storage.server_repo.delete_server(
                                session, s_name
                            )
                            app_context.state.servers.remove(s_name)
                            app_context.state.servers.remove_dirty_server(s_name)
                for s_name in orphaned_db_servers:
                    deleted.append(f"db:server:{s_name}")
            except Exception as error:
                failures["db:servers"] = classify_failure(error).error

    config_root = Path(app_context.config_dir)
    for scoped_parent in (
        config_root / "runtime" / "servers",
        config_root / "logs" / "servers",
    ):
        if not scoped_parent.is_dir():
            continue
        try:
            for sub in sorted(scoped_parent.iterdir()):
                if sub.is_dir() and sub.name not in installed_servers:
                    try:
                        if not dry_run:
                            shutil.rmtree(sub)
                        deleted.append(str(sub))
                    except OSError as error:
                        failures[str(sub)] = classify_failure(error).error
        except OSError as error:
            failures[str(scoped_parent)] = classify_failure(error).error

    # Clean stale unverified PID files for installed servers and web runtime
    server_procs = await get_verified_server_processes(
        app_context, sorted(installed_servers)
    )
    for s_name in sorted(installed_servers):
        if s_name in server_procs:
            continue
        pid_file = (
            config_root / "runtime" / "servers" / s_name / f"bedrock_{s_name}.pid"
        )
        if pid_file.is_file():
            try:
                if not dry_run:
                    pid_file.unlink()
                deleted.append(str(pid_file))
            except OSError as error:
                failures[str(pid_file)] = classify_failure(error).error

    web_proc = await get_verified_web_process(app_context)
    if web_proc is None:
        for web_runtime_file in (
            config_root / "runtime" / "web_server.pid",
            config_root / "runtime" / "web_server.control.json",
        ):
            if web_runtime_file.is_file():
                try:
                    if not dry_run:
                        web_runtime_file.unlink()
                    deleted.append(str(web_runtime_file))
                except OSError as error:
                    failures[str(web_runtime_file)] = classify_failure(error).error

    return CleanupResult(deleted=deleted, retained=retained, failures=failures)


async def _cleanup_orphaned_addons_async(
    app_context: AppContext, dry_run: bool = False
) -> CleanupResult:
    """Clean orphaned pack entries from world activation JSON files across servers."""
    servers_dir_val = app_context.settings.get("paths.servers")
    deleted: list[str] = []
    retained: list[str] = []
    failures: dict[str, FailureInfo] = {}

    if not servers_dir_val or not os.path.isdir(str(servers_dir_val)):
        return CleanupResult(deleted=deleted, retained=retained, failures=failures)

    try:
        server_names = sorted(
            entry.name
            for entry in Path(str(servers_dir_val)).iterdir()
            if entry.is_dir()
        )
    except OSError as error:
        raise FileOperationError("Cannot scan servers directory.") from error

    for server_name in server_names:
        try:
            server = app_context.get_server(server_name, require_installation=False)
            if not await server.is_installed():
                continue
            inventory = await server.addons.list_installed_addons()
        except Exception as error:
            failures[server_name] = classify_failure(error).error
            continue

        for pack_key, pack_type in (
            ("behavior_packs", "behavior"),
            ("resource_packs", "resource"),
        ):
            for pack in inventory.get(pack_key, []):
                pack_uuid = str(pack.get("uuid") or "")
                label = f"{server_name}:{pack_type}:{pack_uuid}"
                if pack.get("status") == "ORPHANED" and pack_uuid:
                    try:
                        if not dry_run:
                            await server.addons.disable_addon(pack_uuid, pack_type)
                        deleted.append(label)
                    except Exception as error:
                        failures[label] = classify_failure(error).error
                elif pack_uuid:
                    retained.append(label)

    return CleanupResult(deleted=deleted, retained=retained, failures=failures)


def _report_result(
    title: str,
    result: CleanupResult,
    item_label: str,
    dry_run: bool = False,
) -> bool:
    """Display consistent CLI feedback for one cleanup step."""
    if result.failures:
        raise click.ClickException(
            f"{title} cleanup incomplete: {len(result.deleted)} cleaned, {len(result.failures)} failed."
        )
    count = len(result.deleted)
    if count > 0:
        verb = "Would clean up" if dry_run else "Cleaned up"
        click.secho(f"Success: {verb} {count} {item_label}.", fg="green")
        for item in result.deleted:
            click.echo(f"  - {item}")
        return True
    click.secho(f"Info: No {item_label} found to clean.", fg="cyan")
    return False


# --- The Click Command ---


@click.command("cleanup")
@click.option(
    "-c",
    "--cache",
    is_flag=True,
    help="Clean up Python bytecode cache files (__pycache__).",
)
@click.option(
    "-l",
    "--logs",
    is_flag=True,
    help="Clean up rotated and historical application and server log files.",
)
@click.option(
    "--log-dir",
    "log_dir_override",
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
    help="Override the default log directory from settings.",
)
@click.option(
    "-p",
    "--plugins",
    is_flag=True,
    help="Clean up orphaned plugin DB entries, settings, and private plugin directories.",
)
@click.option(
    "-s",
    "--servers",
    is_flag=True,
    help="Clean up orphaned server DB entries, runtime directories, and log directories.",
)
@click.option(
    "-a",
    "--addons",
    is_flag=True,
    help="Clean up orphaned addon entries from server world activation JSON files.",
)
@click.option(
    "--orphans",
    is_flag=True,
    help="Clean up all orphaned records and directories (--plugins --servers --addons).",
)
@click.option(
    "--all",
    "all_targets",
    is_flag=True,
    help="Run all cleanup targets (--cache --logs --plugins --servers --addons).",
)
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    help="Preview items that would be cleaned without deleting or modifying anything.",
)
@click.pass_context
def cleanup(
    ctx: click.Context,
    cache: bool,
    logs: bool,
    log_dir_override: Optional[Path],
    plugins: bool,
    servers: bool,
    addons: bool,
    orphans: bool,
    all_targets: bool,
    dry_run: bool,
):
    """Clean up caches, logs, and orphaned plugin/server/addon records and directories."""
    logger.info("Running cleanup command...")
    app_context: AppContext = ctx.obj["app_context"]

    if all_targets:
        cache = logs = plugins = servers = addons = True
    elif orphans:
        plugins = servers = addons = True

    if not any((cache, logs, plugins, servers, addons)):
        click.secho(
            "No cleanup options specified. Use --cache, --logs, --plugins, --servers, --addons, --orphans, or --all.",
            fg="yellow",
        )
        logger.warning("Cleanup command run without any action flags.")
        return

    if dry_run:
        click.secho(
            "[DRY RUN] Previewing cleanup actions (no changes will be made)...",
            fg="yellow",
            bold=True,
        )

    was_anything_cleaned = False

    if cache:
        click.secho("\nCleaning Python cache files (__pycache__)...", bold=True)
        try:
            result = _cleanup_pycache(dry_run=dry_run)
        except FileOperationError as error:
            raise click.ClickException(str(error)) from error
        if result.failures:
            raise click.ClickException(
                f"Cache cleanup incomplete: {len(result.deleted)} deleted, {len(result.failures)} failed."
            )
        deleted_count = len(result.deleted)
        if deleted_count > 0:
            verb = "Would clean up" if dry_run else "Cleaned up"
            click.secho(
                f"Success: {verb} {deleted_count} __pycache__ director(ies).",
                fg="green",
            )
            logger.info("Cleaned %s __pycache__ directories.", deleted_count)
            was_anything_cleaned = True
        else:
            click.secho("Info: No __pycache__ directories found to clean.", fg="cyan")
            logger.info("No __pycache__ directories found.")

    if logs:
        click.secho("\nCleaning log files...", bold=True)

        final_log_dir = log_dir_override
        if not final_log_dir:
            settings_log_dir = app_context.log_dir
            if settings_log_dir:
                final_log_dir = Path(settings_log_dir)

        if not final_log_dir:
            msg = (
                "Log directory not specified via --log-dir or in application settings."
            )
            click.secho(f"Error: {msg}", fg="red")
            logger.error("Cannot clean logs: %s", msg)
            raise click.Abort()

        click.echo(f"Targeting log directory: {final_log_dir}")
        try:
            result = _cleanup_log_files(
                final_log_dir, dry_run=dry_run, app_context=app_context
            )
        except FileOperationError as error:
            raise click.ClickException(str(error)) from error
        if result.failures:
            raise click.ClickException(
                f"Log cleanup incomplete: {len(result.deleted)} deleted, {len(result.failures)} failed."
            )
        deleted_count = len(result.deleted)

        if deleted_count > 0:
            verb = "Would clean up" if dry_run else "Cleaned up"
            click.secho(
                f"Success: {verb} {deleted_count} log file(s) from '{final_log_dir}'.",
                fg="green",
            )
            logger.info("Cleaned %s log files from '%s'.", deleted_count, final_log_dir)
            was_anything_cleaned = True
        else:
            click.secho(
                f"Info: No log files found to clean in '{final_log_dir}'.", fg="cyan"
            )
            logger.info("No log files found in '%s'.", final_log_dir)

    if plugins:
        click.secho("\nCleaning orphaned plugin records and directories...", bold=True)
        result = asyncio.run(
            _cleanup_orphaned_plugins_async(app_context, dry_run=dry_run)
        )
        if _report_result("Plugin", result, "orphaned plugin item(s)", dry_run=dry_run):
            was_anything_cleaned = True

    if servers:
        click.secho("\nCleaning orphaned server records and directories...", bold=True)
        result = asyncio.run(
            _cleanup_orphaned_servers_async(app_context, dry_run=dry_run)
        )
        if _report_result("Server", result, "orphaned server item(s)", dry_run=dry_run):
            was_anything_cleaned = True

    if addons:
        click.secho("\nCleaning orphaned world addon activations...", bold=True)
        try:
            result = asyncio.run(
                _cleanup_orphaned_addons_async(app_context, dry_run=dry_run)
            )
        except FileOperationError as error:
            raise click.ClickException(str(error)) from error
        if _report_result(
            "Addon", result, "orphaned addon activation(s)", dry_run=dry_run
        ):
            was_anything_cleaned = True

    if was_anything_cleaned:
        logger.info("Cleanup operations finished successfully.")
    else:
        logger.info("Cleanup operations finished, nothing was cleaned.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleanup()
