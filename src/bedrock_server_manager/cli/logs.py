# bedrock_server_manager/cli/logs.py
"""Define the ``bsm logs`` command for listing, selecting, viewing, and streaming logs."""

import asyncio
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple

import click
import questionary

from ..context import AppContext
from ..core.system import process as system_process
from ..logging import get_application_log_path
from ..web.process import WebProcessPaths, read_control, verify_web_owner

if TYPE_CHECKING:
    import psutil


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KiB"
    return f"{num_bytes / (1024 * 1024):.1f} MiB"


def _format_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _is_cli_own_log(path: Path, log_dir: Path) -> bool:
    """Return True if ``path`` is the log file opened by this short-lived CLI process."""
    cli_log = get_application_log_path(str(log_dir))
    if cli_log:
        try:
            if path.resolve() == Path(cli_log).resolve():
                return True
        except OSError:
            pass
    return f"_{os.getpid()}_" in path.name


async def get_verified_web_process(
    app_context: AppContext,
) -> Optional["psutil.Process"]:
    """Return the verified background web server process if one is running."""
    if not app_context.config_dir:
        return None
    paths = WebProcessPaths(
        config_dir=app_context.config_dir,
        data_dir=app_context.data_dir,
        db_url=app_context.db_url,
    )
    try:
        record = read_control(paths)
    except Exception:
        record = None
    pid: Optional[int] = record.pid if record is not None else None
    if pid is None and paths.pid_file.is_file():
        pid = await system_process.read_pid_from_file(str(paths.pid_file))
    if pid is None or pid == os.getpid():
        return None
    try:
        return await verify_web_owner(paths, pid, record)
    except Exception:
        return None


async def get_verified_server_processes(
    app_context: AppContext, server_names: Iterable[str]
) -> dict[str, "psutil.Process"]:
    """Return ``{server_name: psutil.Process}`` for servers with a verified running PID."""
    verified: dict[str, "psutil.Process"] = {}
    if not app_context.config_dir:
        return verified
    servers_base = app_context.settings.get("paths.servers")
    if not servers_base:
        return verified
    for server_name in server_names:
        server_dir = os.path.join(str(servers_base), server_name)
        try:
            proc = await system_process.get_verified_bedrock_process(
                server_name, server_dir, app_context.config_dir
            )
            if proc is not None:
                verified[server_name] = proc
        except Exception:
            continue
    return verified


def resolve_active_app_log(
    log_dir: Path, web_process: Optional["psutil.Process"]
) -> Tuple[List[Path], Optional[Path], Optional[int]]:
    """Return ``(files_newest_first, active_web_log, web_pid)`` for application logs.

    Excludes the current CLI invocation's own log file when other application logs exist.
    Only marks a file as active when a verified background web server process owns it.
    """
    if not log_dir.is_dir():
        return ([], None, None)
    all_files = [
        p
        for p in log_dir.iterdir()
        if p.is_file() and (p.suffix == ".log" or ".log." in p.name)
    ]
    all_files.sort(key=os.path.getmtime, reverse=True)
    non_cli_files = [p for p in all_files if not _is_cli_own_log(p, log_dir)]
    files = non_cli_files if non_cli_files else all_files

    if web_process is None:
        return (files, None, None)

    web_pid = web_process.pid
    pid_token = f"_{web_pid}_"
    for candidate in files:
        if candidate.suffix == ".log" and pid_token in candidate.name:
            return (files, candidate, web_pid)

    fixed = log_dir / "bedrock_server_manager.log"
    if fixed in files:
        return (files, fixed, web_pid)

    return (files, None, web_pid)


def resolve_server_logs(
    log_dir: Path,
    server_name: str,
    server_process: Optional["psutil.Process"] = None,
) -> Tuple[List[Path], Optional[Path], Optional[int]]:
    """Return ``(files_newest_first, active_server_log, server_pid)`` for one server.

    Only marks a log file as active when ``server_process`` is a verified running process.
    """
    s_dir = log_dir / "servers" / server_name
    if not s_dir.is_dir():
        return ([], None, None)
    files = [
        p
        for p in s_dir.iterdir()
        if p.is_file() and (p.suffix == ".log" or ".log." in p.name)
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    if server_process is None or not files:
        return (files, None, None)
    primary_logs = [p for p in files if p.suffix == ".log"]
    active = primary_logs[0] if primary_logs else files[0]
    return (files, active, server_process.pid)


def _discover_all_server_names(app_context: AppContext, log_dir: Path) -> List[str]:
    names = set(app_context.state.servers.servers.keys())
    servers_dir = app_context.settings.get("paths.servers")
    if servers_dir and os.path.isdir(str(servers_dir)):
        try:
            for entry in Path(str(servers_dir)).iterdir():
                if entry.is_dir():
                    names.add(entry.name)
        except OSError:
            pass
    servers_log_dir = log_dir / "servers"
    if servers_log_dir.is_dir():
        try:
            for entry in servers_log_dir.iterdir():
                if entry.is_dir():
                    names.add(entry.name)
        except OSError:
            pass
    return sorted(names)


def _read_tail_lines(path: Path, lines: int) -> Tuple[str, int]:
    """Return ``(tail_text, end_byte_offset)`` from ``path``."""
    with open(path, "rb") as f:
        if lines <= 0:
            data = f.read()
            return (
                data.decode("utf-8", errors="replace").replace("\r\n", "\n"),
                f.tell(),
            )
        tail: deque[bytes] = deque(maxlen=lines)
        for raw_line in f:
            tail.append(raw_line)
        end_pos = f.tell()
    return (
        b"".join(tail).decode("utf-8", errors="replace").replace("\r\n", "\n"),
        end_pos,
    )


def _follow_file(path: Path, start_pos: int, poll_interval: float = 0.25) -> None:
    """Stream appended lines from ``path`` until interrupted."""
    click.secho(
        f"\n--- Following {path.name} (Ctrl+C to stop) ---", fg="cyan", bold=True
    )
    pos = start_pos
    try:
        while True:
            if path.is_file():
                size = path.stat().st_size
                if size < pos:
                    pos = 0
                if size > pos:
                    with open(path, "rb") as f:
                        f.seek(pos)
                        chunk = f.read()
                        pos = f.tell()
                    if chunk:
                        click.echo(chunk.decode("utf-8", errors="replace"), nl=False)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        click.secho("\nStopped following log.", fg="yellow")


def _file_status_tag(
    file_path: Path,
    files: List[Path],
    active_path: Optional[Path],
    active_pid: Optional[int],
) -> str:
    if active_path is not None and file_path == active_path:
        return f" [ACTIVE - PID {active_pid}]" if active_pid else " [ACTIVE]"
    if files and file_path == files[0]:
        return " [LATEST]"
    return ""


def _print_log_inventory(
    app_context: AppContext,
    log_dir: Path,
    web_proc: Optional["psutil.Process"],
    server_procs: dict[str, "psutil.Process"],
) -> None:
    app_files, app_active, web_pid = resolve_active_app_log(log_dir, web_proc)
    web_status = f"running (PID {web_pid})" if web_proc is not None else "stopped"
    click.secho(f"\nApplication Logs (Web Server: {web_status}):", bold=True)
    if not app_files:
        click.echo("  (no application log files found)")
    else:
        for f in app_files:
            stat = f.stat()
            marker = _file_status_tag(f, app_files, app_active, web_pid)
            click.echo(
                f"  - {f.name} ({_format_size(stat.st_size)}, {_format_mtime(stat.st_mtime)}){marker}"
            )

    for server_name in _discover_all_server_names(app_context, log_dir):
        s_proc = server_procs.get(server_name)
        s_files, s_active, s_pid = resolve_server_logs(log_dir, server_name, s_proc)
        s_status = f"running (PID {s_pid})" if s_proc is not None else "stopped"
        click.secho(f"\nServer Logs [{server_name}] ({s_status}):", bold=True)
        if not s_files:
            click.echo("  (no server log files found)")
        else:
            for f in s_files:
                stat = f.stat()
                marker = _file_status_tag(f, s_files, s_active, s_pid)
                click.echo(
                    f"  - {f.name} ({_format_size(stat.st_size)}, {_format_mtime(stat.st_mtime)}){marker}"
                )


@click.command("logs")
@click.option(
    "-a",
    "--app",
    "use_app",
    is_flag=True,
    help="Select the background web server's active (or latest) application log.",
)
@click.option(
    "-s",
    "--server",
    "server_name",
    type=str,
    help="Select logs for a specific Bedrock server.",
)
@click.option(
    "--file",
    "file_selector",
    type=str,
    help="Select a specific log file name or path.",
)
@click.option(
    "-l",
    "--list",
    "list_only",
    is_flag=True,
    help="List available application and server log files with verified PID status.",
)
@click.option(
    "-n",
    "--lines",
    type=click.IntRange(min=0),
    default=50,
    show_default=True,
    help="Number of trailing lines to show (0 for entire file).",
)
@click.option(
    "-f",
    "--follow",
    is_flag=True,
    help="Stream new log output continuously (like tail -f).",
)
@click.pass_context
def logs(
    ctx: click.Context,
    use_app: bool,
    server_name: Optional[str],
    file_selector: Optional[str],
    list_only: bool,
    lines: int,
    follow: bool,
):
    """List, select, view, or live-stream application and server logs."""
    app_context: AppContext = ctx.obj["app_context"]
    if not app_context.log_dir:
        raise click.ClickException("Log directory is not configured.")
    log_dir = Path(app_context.log_dir)

    if use_app and server_name:
        raise click.ClickException("Cannot specify both --app and --server.")

    all_servers = _discover_all_server_names(app_context, log_dir)
    web_proc = asyncio.run(get_verified_web_process(app_context))
    server_procs = asyncio.run(get_verified_server_processes(app_context, all_servers))

    if list_only:
        _print_log_inventory(app_context, log_dir, web_proc, server_procs)
        return

    target_path: Optional[Path] = None

    # 1. Explicit --file selector
    if file_selector:
        candidate = Path(file_selector)
        if candidate.is_file():
            target_path = candidate.resolve()
        elif server_name:
            s_candidate = log_dir / "servers" / server_name / file_selector
            if s_candidate.is_file():
                target_path = s_candidate.resolve()
        else:
            a_candidate = log_dir / file_selector
            if a_candidate.is_file():
                target_path = a_candidate.resolve()
        if target_path is None:
            raise click.ClickException(f"Log file '{file_selector}' not found.")

    # 2. Explicit --app or --server
    elif use_app:
        files, active_path, _ = resolve_active_app_log(log_dir, web_proc)
        target_path = active_path or (files[0] if files else None)
        if target_path is None:
            raise click.ClickException("No application log files found.")
    elif server_name:
        s_proc = server_procs.get(server_name)
        files, active_path, _ = resolve_server_logs(log_dir, server_name, s_proc)
        target_path = active_path or (files[0] if files else None)
        if target_path is None:
            raise click.ClickException(
                f"No log files found for server '{server_name}'."
            )

    # 3. Interactive selection when no target flags were provided
    else:
        web_tag = (
            f" [ACTIVE - PID {web_proc.pid}]" if web_proc is not None else " [stopped]"
        )
        sources: list[questionary.Choice] = [
            questionary.Choice(
                f"Application Logs (Web Server{web_tag})", value=("app", None)
            )
        ]
        for s_name in all_servers:
            s_proc = server_procs.get(s_name)
            s_tag = (
                f" [ACTIVE - PID {s_proc.pid}]" if s_proc is not None else " [stopped]"
            )
            sources.append(
                questionary.Choice(f"Server: {s_name}{s_tag}", value=("server", s_name))
            )

        selected_source = questionary.select(
            "Select log source:", choices=sources
        ).ask()
        if not selected_source:
            return

        kind, chosen_server = selected_source
        if kind == "app":
            files, active, active_pid = resolve_active_app_log(log_dir, web_proc)
        else:
            s_proc = server_procs.get(str(chosen_server))
            files, active, active_pid = resolve_server_logs(
                log_dir, str(chosen_server), s_proc
            )

        if not files:
            raise click.ClickException("No log files found for the selected source.")

        file_choices: list[questionary.Choice] = []
        for f in files:
            stat = f.stat()
            tag = _file_status_tag(f, files, active, active_pid)
            label = f"{f.name} ({_format_size(stat.st_size)}, {_format_mtime(stat.st_mtime)}){tag}"
            file_choices.append(questionary.Choice(label, value=f))

        target_path = questionary.select("Select log file:", choices=file_choices).ask()
        if target_path is None:
            return

        if not follow:
            action = questionary.select(
                "Select action:",
                choices=[
                    questionary.Choice(f"View last {lines} lines", value="tail"),
                    questionary.Choice("Follow / stream live (-f)", value="follow"),
                    questionary.Choice("View entire file", value="all"),
                ],
            ).ask()
            if not action:
                return
            if action == "follow":
                follow = True
            elif action == "all":
                lines = 0

    assert target_path is not None
    click.secho(f"=== {target_path} ===", fg="green", bold=True)
    try:
        text, end_pos = _read_tail_lines(target_path, lines)
    except OSError as error:
        raise click.ClickException(f"Could not read log file: {error}") from error

    if text:
        click.echo(text, nl=not text.endswith("\n"))
    else:
        click.secho("(log file is empty)", fg="yellow")

    if follow:
        _follow_file(target_path, end_pos)
