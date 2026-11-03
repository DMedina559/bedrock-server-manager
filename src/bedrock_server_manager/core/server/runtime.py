"""Generation-owned BDS pipes, protocol waits and bounded asynchronous effects."""

import asyncio
import contextlib
import logging
import re
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, AsyncIterator, Callable
from uuid import uuid4

from ...error import BackupRestoreError, SendCommandError, ServerProcessError
from ...events.player import PlayerSnapshot, publish_player_snapshot
from ...utils.threads import run_in_thread

if TYPE_CHECKING:
    from ...db.storage import Storage
    from ..bedrock_server import BedrockServer

logger = logging.getLogger(__name__)
_PREFIX = re.compile(r"^(?:\[[^\]\r\n]{0,120}\]\s*)*")
_PLAYER = re.compile(
    r"^Player (connected|disconnected):\s*([^,]+?)(?:,\s*|\s+)xuid:\s*(\d+)(?:\D|$)",
    re.I,
)
_SAVE = re.compile(
    r"^(?:Data saved\. Files are now ready to be copied\.|Data the world is saved:?)\s*(.*)$",
    re.I,
)


def validate_command(command: str) -> bytes:
    if not command or not command.strip():
        raise SendCommandError("Command cannot be empty.")
    if any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in "\u2028\u2029" for c in command):
        raise SendCommandError(
            "Console commands must be a single line without control characters."
        )
    try:
        data = command.encode("utf-8")
    except UnicodeEncodeError as error:
        raise SendCommandError("Command must contain valid UTF-8 text.") from error
    if len(data) > 64 * 1024:
        raise SendCommandError("Console command exceeds 64 KiB.")
    return data + b"\n"


def kick_command(name: str, reason: str) -> str:
    # Bedrock uses double-quoted arguments, not shell escaping.
    validate_command(name)
    validate_command(reason)
    quoted = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'kick "{quoted}" {reason}'


class PlayerIdentityWriter:
    """Application-owned pending identities survive individual BDS run shutdown."""

    def __init__(self, storage: "Storage") -> None:
        self.storage = storage
        self.pending: dict[str, str] = {}
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._closing = False
        self.last_error: str | None = None

    def submit(self, name: str, xuid: str) -> None:
        if self._closing:
            raise ServerProcessError("Identity writer is shutting down.")
        if xuid not in self.pending and len(self.pending) >= 4096:
            raise ServerProcessError(
                "Pending identity capacity exhausted; consult persisted server output."
            )
        self.pending[xuid] = name
        self._wake.set()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._work(), name="player-identities")

    async def flush(self) -> None:
        batch = dict(list(self.pending.items())[:256])
        if not batch:
            return
        await self.storage.save_players(
            [{"xuid": xuid, "name": name} for xuid, name in batch.items()]
        )
        for xuid, name in batch.items():
            if self.pending.get(xuid) == name:
                self.pending.pop(xuid, None)
        self.last_error = None

    async def _work(self) -> None:
        while not self._closing:
            await self._wake.wait()
            self._wake.clear()
            while self.pending and not self._closing:
                try:
                    await self.flush()
                except Exception as error:
                    self.last_error = type(error).__name__
                    logger.warning(
                        "Player identity persistence unavailable; retaining pending records",
                        exc_info=True,
                    )
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0)

    async def shutdown(self) -> None:
        self._closing = True
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        while self.pending:
            await self.flush()  # Failure propagates; dependencies must remain available.


@dataclass(frozen=True)
class OutputLine:
    generation: str
    sequence: int
    line: str


class OwnedBDSRun:
    """One reader and exit observer own one process generation until finalization."""

    def __init__(
        self,
        server: "BedrockServer",
        process: asyncio.subprocess.Process,
        log_path: str,
        log_file,
        on_exit: Callable[["OwnedBDSRun"], None],
    ) -> None:
        self.server = server
        self.process = process
        self.generation = uuid4().hex
        self.log_path = log_path
        self.log_file = log_file
        self.on_exit = on_exit
        self.phase = "STARTING"
        self.ready = False
        self.stop_requested = False
        self.failure: str | None = None
        self.sequence = 0
        self.players: dict[str, str] = {}
        self.sessions: dict[str, int] = {}
        self.ready_event = asyncio.Event()
        self.reader_done = asyncio.Event()
        self.closed = asyncio.Event()
        self._effects = asyncio.Event()
        self._notifications_idle = asyncio.Event()
        self._bans_changed = asyncio.Event()
        self._ban_revision = 0
        self._write_lock = asyncio.Lock()
        self._command_slots = asyncio.Semaphore(64)
        self.protocol_lock = asyncio.Lock()
        self._raw: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=128)
        self.queued_bytes = 0
        self.dropped_bytes = 0
        self.persisted_offset = 0
        self.journal: deque[tuple[int, bytes]] = deque(maxlen=32)
        self._partial = bytearray()
        self._waiters: dict[asyncio.Future, tuple[str, bool, int]] = {}
        self._lines: deque[OutputLine] = deque()
        self._line_bytes = 0
        self._replay_floor = 0
        self._save_bytes = 0
        self.workers: dict[str, asyncio.Task] = {}
        self._phases: deque[dict] = deque(maxlen=32)
        self._last_queued_phase: str | None = None
        self._deltas: deque[dict] = deque(maxlen=1024)
        self._save_future: asyncio.Future[list[tuple[str, int]]] | None = None
        self._save_header = False
        self._save_entries: list[tuple[str, int]] = []
        self._protocol_task: asyncio.Task | None = None
        self.ban_available = False
        self.ban_error: str | None = None
        self.tasks: list[asyncio.Task] = []
        self.exit_task: asyncio.Task | None = None
        self._failure_task: asyncio.Task | None = None
        self._stop_task: asyncio.Task | None = None
        self.exit_reason = "unexpected"

    def current(self) -> bool:
        return self.server.process.run is self

    def start(self) -> None:
        self.publish()
        for name, coroutine in (
            ("log-writer", self._log_writer()),
            ("output", self._read()),
            ("notifications", self._notify()),
            ("bans", self._enforce_bans()),
            ("readiness", self._readiness()),
        ):
            task = asyncio.create_task(
                coroutine,
                name=f"bds:{self.server.server_name}:{self.generation}:{name}",
            )
            self.workers[name] = task
            self.tasks.append(task)
        self.exit_task = asyncio.create_task(
            self._exited(), name=f"bds:{self.server.server_name}:exit"
        )
        self._effects.set()
        self._bans_changed.set()

    def publish(self) -> None:
        if not self.current():
            return
        payload = self.runtime_payload()
        if self._last_queued_phase != self.phase:
            if len(self._phases) == self._phases.maxlen:
                raise ServerProcessError("Runtime transition capacity exhausted.")
            self._phases.append(payload)
            self._last_queued_phase = self.phase
        self.server._runtime_state.update_server_runtime(
            self.server.server_name,
            running=self.process.returncode is None,
            pid=self.process.pid if self.process.returncode is None else None,
            generation=self.generation,
            ready=self.ready,
            phase=self.phase,
            process_owned=self.process.returncode is None,
            command_available=self.process.returncode is None
            and self.process.stdin is not None
            and not self.process.stdin.is_closing(),
            output_source="pipe",
            output_available=not self.reader_done.is_set() and self.failure is None,
            players_available=self.failure is None,
            players_online=len(self.players),
            players=[
                {"xuid": xuid, "name": name} for xuid, name in self.players.items()
            ],
            process_observed_at=time.time(),
            output_error=self.failure,
            output_queued_bytes=self.queued_bytes,
            output_dropped_bytes=self.dropped_bytes,
            exit_code=self.process.returncode,
            exit_reason=self.failure or self.exit_reason,
            ban_enforcement_available=self.ban_available and not self.stop_requested,
            ban_error=self.ban_error,
        )

    async def send(
        self, command: str, *, shutdown: bool = False, timeout: float | None = None
    ) -> None:
        data = validate_command(command)
        if (
            command.strip().lower() in {"save hold", "save query", "save resume"}
            and self.protocol_lock.locked()
            and asyncio.current_task() is not self._protocol_task
        ):
            raise SendCommandError(
                "A save protocol session already owns the console response stream."
            )
        deadline = (
            timeout
            if timeout is not None
            else self.server.settings.get("lifecycle.command_timeout_seconds", 5.0)
        )
        try:
            async with asyncio.timeout(deadline):
                if not shutdown:
                    await self._command_slots.acquire()
                try:
                    async with self._write_lock:
                        if (
                            not self.current()
                            or self.process.returncode is not None
                            or self.process.stdin is None
                        ):
                            raise SendCommandError(
                                "Process generation no longer has a command channel."
                            )
                        if self.stop_requested and not shutdown:
                            raise SendCommandError(
                                "Process is stopping; new commands are rejected."
                            )
                        self.process.stdin.write(data)
                        await self.process.stdin.drain()
                finally:
                    if not shutdown:
                        self._command_slots.release()
        except (TimeoutError, BrokenPipeError, ConnectionResetError) as error:
            raise SendCommandError(
                "Console delivery failed or timed out; delivery may be uncertain."
            ) from error

    def _fail(self, reason: str) -> None:
        if self.failure is not None:
            return
        self.failure = reason
        self.phase = "ERROR"
        self.publish()
        self._fail_waiters(reason)
        self._effects.set()
        if not self.stop_requested and self.process.returncode is None:
            self._failure_task = asyncio.create_task(
                self.stop(), name=f"bds:{self.server.server_name}:output-failure-stop"
            )
            self._failure_task.add_done_callback(self._consume_failure)

    @staticmethod
    def _consume_failure(task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.error(
                "Output-failure stop did not complete", exc_info=task.exception()
            )

    async def _read(self) -> None:
        try:
            if self.process.stdout is None:
                raise ServerProcessError("Owned BDS has no stdout pipe.")
            while True:
                data = await self.process.stdout.read(64 * 1024)
                if not data:
                    break
                try:
                    self._raw.put_nowait(data)
                    self.queued_bytes += len(data)
                except asyncio.QueueFull:
                    self.dropped_bytes += len(data)
                    self._fail("Raw output persistence capacity exhausted.")
                if not self.current():
                    self._fail_waiters("Process generation replaced.")
                elif self.failure is None:
                    try:
                        self.feed(data)
                    except Exception as error:
                        self._partial.clear()
                        self._fail(f"Output reduction failed: {type(error).__name__}")
                await asyncio.sleep(0)
            # Keep the raw EOF fragment in the log, but never promote an
            # incomplete line into a player/protocol record.
            self._partial.clear()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("BDS output reader failed")
            self._fail(type(error).__name__)
        finally:
            self.reader_done.set()
            # A full queue already wakes the writer; it also checks reader_done.
            with contextlib.suppress(asyncio.QueueFull):
                self._raw.put_nowait(None)
            if self.process.returncode is None and not self.stop_requested:
                self._fail("Output pipe closed while process remained alive.")

    def feed(self, data: bytes) -> None:
        self._partial.extend(data)
        limit = 8 * 1024 * 1024 if self._save_future is not None else 256 * 1024
        while b"\n" in self._partial and self.failure is None:
            raw, _, remainder = self._partial.partition(b"\n")
            self._partial = bytearray(remainder)
            if len(raw) > limit:
                self._fail("Output line exceeds parser capacity.")
                return
            self._line(bytes(raw).rstrip(b"\r"))
        if len(self._partial) > limit:
            self._partial.clear()
            self._fail("Unterminated output line exceeds parser capacity.")

    def _line(self, raw: bytes) -> None:
        self.sequence += 1
        line = raw.decode("utf-8", errors="replace")
        record = OutputLine(self.generation, self.sequence, line)
        self._lines.append(record)
        self._line_bytes += len(line.encode("utf-8"))
        while self._lines and (
            len(self._lines) > 256 or self._line_bytes > 1024 * 1024
        ):
            evicted = self._lines.popleft()
            self._line_bytes -= len(evicted.line.encode("utf-8"))
            self._replay_floor = evicted.sequence
        for future, (text, exact, after) in list(self._waiters.items()):
            if (
                not future.done()
                and record.sequence > after
                and (line == text if exact else text in line)
            ):
                future.set_result(record)
        message = _PREFIX.sub("", line).strip()
        if (
            message.lower() in {"server started.", "server started"}
            and self.phase == "STARTING"
            and not self.stop_requested
            and self.current()
        ):
            self.ready = True
            self.phase = "RUNNING"
            self.ready_event.set()
            self.publish()
            self._effects.set()
        match = _PLAYER.match(message)
        if match and self.current():
            action, name, xuid = match.groups()
            name = name.strip()
            if action.lower() == "connected":
                self.players[xuid] = name
                self.sessions[xuid] = self.sequence
                if self.server.identity_writer is not None:
                    self.server.identity_writer.submit(name, xuid)
            else:
                self.players.pop(xuid, None)
                self.sessions.pop(xuid, None)
            if len(self._deltas) == self._deltas.maxlen:
                self._fail("Player notification capacity exhausted.")
                return
            self._deltas.append(
                {
                    "server_name": self.server.server_name,
                    "generation": self.generation,
                    "sequence": self.sequence,
                    "name": name,
                    "xuid": xuid,
                    "action": action.lower(),
                    "reason": "observed",
                }
            )
            self.publish()
            self._effects.set()
            self._bans_changed.set()
        self._save_line(message)

    def _save_line(self, message: str) -> None:
        future = self._save_future
        if future is None or future.done():
            return
        header = _SAVE.match(message)
        if header:
            # A fresh query acknowledgement closes the previous frame, including
            # multiline lists. Never accept just the first nonempty fragment.
            if self._save_header and self._save_entries:
                future.set_result(list(self._save_entries))
                return
            self._save_header = True
            message = header.group(1).strip()
            if not message:
                return
        if not self._save_header:
            return
        if not message:
            if self._save_entries:
                future.set_result(list(self._save_entries))
            return
        entries = []
        for item in message.split(","):
            item = item.strip()
            if not item:
                continue
            path, separator, size = item.rpartition(":")
            if not separator or not path or not size.strip().isdigit():
                return
            entries.append((path.strip(), int(size)))
        if len(self._save_entries) + len(entries) > 100000:
            self._fail("Save response entry capacity exhausted.")
            return
        self._save_bytes += len(message.encode("utf-8"))
        if self._save_bytes > 8 * 1024 * 1024:
            self._fail("Save response byte capacity exhausted.")
            return
        self._save_entries.extend(entries)

    async def _log_writer(self) -> None:
        try:
            while not self.reader_done.is_set() or not self._raw.empty():
                data = await self._raw.get()
                if data is None:
                    break

                def write() -> None:
                    self.log_file.write(data)
                    self.log_file.flush()

                await run_in_thread(write)
                self.journal.append((self.persisted_offset, data))
                self.persisted_offset += len(data)
                self.queued_bytes -= len(data)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._fail(f"Log persistence failed: {type(error).__name__}")
        finally:
            await run_in_thread(self.log_file.close)

    async def _notify(self) -> None:
        projected_phase = None
        while True:
            await self._effects.wait()
            self._effects.clear()
            self._notifications_idle.clear()
            if not self.current():
                self._deltas.clear()
                self._notifications_idle.set()
                return
            try:
                events = self.server.events
                while self._phases:
                    transition = self._phases[0]
                    if events is not None and events.accepting:
                        if not transition.get("runtime_delivered"):
                            receipt = await events.emit(
                                "after_server_runtime_change",
                                {
                                    k: v
                                    for k, v in transition.items()
                                    if not k.endswith("_delivered")
                                },
                            )
                            if receipt.rejection_reason in {"capacity", "depth_limit"}:
                                break
                            transition["runtime_delivered"] = True
                        if (
                            transition["ready"]
                            and transition["phase"] == "RUNNING"
                            and not transition.get("ready_delivered")
                        ):
                            receipt = await events.emit(
                                "after_server_ready",
                                {
                                    k: v
                                    for k, v in transition.items()
                                    if not k.endswith("_delivered")
                                },
                            )
                            if receipt.rejection_reason in {"capacity", "depth_limit"}:
                                break
                            transition["ready_delivered"] = True
                    self._phases.popleft()
                if projected_phase != self.phase:
                    phase = self.phase
                    try:
                        await self.server.set_status_in_config(phase)
                    except Exception:
                        logger.warning(
                            "Legacy status projection failed; retrying", exc_info=True
                        )
                        self._effects.set()
                    else:
                        projected_phase = phase
                if self._phases:
                    self._effects.set()
                while self._deltas:
                    delta = self._deltas[0]
                    if events is not None and events.accepting:
                        receipt = await events.emit(
                            (
                                "after_server_player_connected"
                                if delta["action"] == "connected"
                                else "after_server_player_disconnected"
                            ),
                            delta,
                        )
                        if receipt.rejection_reason in {"capacity", "depth_limit"}:
                            await asyncio.sleep(0.1)
                            self._effects.set()
                            break
                    self._deltas.popleft()
                if events is not None and events.accepting:
                    receipt = await publish_player_snapshot(
                        events,
                        PlayerSnapshot(
                            server_name=self.server.server_name,
                            player_count=len(self.players),
                            players=[
                                {"xuid": xuid, "name": name}
                                for xuid, name in self.players.items()
                            ],
                        ),
                    )
                    if receipt.rejection_reason in {"capacity", "depth_limit"}:
                        await asyncio.sleep(0.1)
                        self._effects.set()
                if not self._effects.is_set() and not self._deltas and not self._phases:
                    self._notifications_idle.set()
                elif self._effects.is_set():
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Process notifications failed; retrying", exc_info=True)
                await asyncio.sleep(0.5)
                self._effects.set()

    def runtime_payload(self) -> dict:
        return {
            "server_name": self.server.server_name,
            "generation": self.generation,
            "phase": self.phase,
            "ready": self.ready,
            "running": self.process.returncode is None,
            "exit_code": self.process.returncode,
            "reason": self.failure or self.exit_reason,
        }

    def invalidate_bans(self) -> None:
        self._ban_revision += 1
        self._bans_changed.set()

    async def _enforce_bans(self) -> None:
        revision = -1
        bans: dict = {}
        attempts: dict[tuple[str, int], int] = {}
        delivery_errors: dict[tuple[str, int], str] = {}
        while True:
            await self._bans_changed.wait()
            self._bans_changed.clear()
            try:
                storage = self.server.storage
                if storage is None:
                    continue
                if revision != self._ban_revision:
                    expected = self._ban_revision
                    async with storage.transaction() as session:
                        records = await storage.ban_repo.get_bans(
                            session, self.server.server_name
                        )
                    bans = {record.xuid: record for record in records}
                    revision = expected
                    self.ban_available = True
                    self.ban_error = None
                    self.publish()
                for xuid, name in list(self.players.items()):
                    session_id = self.sessions.get(xuid, 0)
                    key = (xuid, session_id)
                    if xuid not in bans or attempts.get(key, 0) >= 3:
                        continue
                    if (
                        not self.current()
                        or self.sessions.get(xuid) != session_id
                        or self.stop_requested
                    ):
                        continue
                    reason = (
                        bans[xuid].reason or "You have been banned from this server."
                    )
                    attempts[key] = attempts.get(key, 0) + 1
                    try:
                        await self.send(kick_command(name, reason))
                    except Exception as error:
                        delivery_errors[key] = (
                            f"Kick delivery failed: {type(error).__name__}"
                        )
                    else:
                        delivery_errors.pop(key, None)
                    if attempts[key] >= 3 and self.sessions.get(xuid) == session_id:
                        delivery_errors.setdefault(
                            key, "Kick retry limit reached; awaiting disconnect."
                        )
                    self._bans_changed.set()
                attempts = {
                    key: value
                    for key, value in attempts.items()
                    if self.sessions.get(key[0]) == key[1]
                }
                delivery_errors = {
                    key: value
                    for key, value in delivery_errors.items()
                    if self.sessions.get(key[0]) == key[1] and key[0] in bans
                }
                self.ban_error = next(iter(delivery_errors.values()), None)
                self.publish()
                if self._bans_changed.is_set():
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.ban_available = False
                self.ban_error = f"Ban refresh failed: {type(error).__name__}"
                self.publish()
                logger.warning(
                    "Ban enforcement failed; retaining retry state", exc_info=True
                )
                await asyncio.sleep(1)
                self._bans_changed.set()

    async def _readiness(self) -> None:
        try:
            async with asyncio.timeout(
                self.server.settings.get("lifecycle.server_ready_timeout_seconds", 60.0)
            ):
                await self.ready_event.wait()
        except TimeoutError:
            if self.current() and self.phase == "STARTING" and not self.stop_requested:
                self._fail("BDS did not report readiness before the startup deadline.")

    def watch(
        self,
        text: str,
        *,
        exact: bool = False,
        after: int | None = None,
        generation: str | None = None,
    ) -> asyncio.Future[OutputLine]:
        if generation is not None and generation != self.generation:
            raise ServerProcessError(
                "Log cursor belongs to a different process generation."
            )
        if after is not None and after < self._replay_floor:
            raise ServerProcessError(
                "Log cursor expired; requested output is no longer retained."
            )
        if not text or len(text.encode()) > 4096 or len(self._waiters) >= 128:
            raise ServerProcessError("Invalid log match or waiter capacity exhausted.")
        if (
            not self.current()
            or self.failure
            or self.closed.is_set()
            or self.reader_done.is_set()
        ):
            raise ServerProcessError("Live process output is unavailable.")
        future: asyncio.Future[OutputLine] = asyncio.get_running_loop().create_future()
        boundary = self.sequence if after is None else after
        self._waiters[future] = (text, exact, boundary)
        if after is not None:
            for record in self._lines:
                if record.sequence > after and (
                    record.line == text if exact else text in record.line
                ):
                    future.set_result(record)
                    break
        future.add_done_callback(lambda done: self._waiters.pop(done, None))
        return future

    async def wait_for_log(
        self,
        text: str,
        *,
        exact: bool = False,
        after: int | None = None,
        generation: str | None = None,
        timeout: float = 30,
    ) -> OutputLine:
        if not 0 < timeout <= 300:
            raise ServerProcessError(
                "Log wait timeout must be between 0 and 300 seconds."
            )
        future = self.watch(text, exact=exact, after=after, generation=generation)
        try:
            async with asyncio.timeout(timeout):
                return await future
        finally:
            future.cancel()
            self._waiters.pop(future, None)

    def _fail_waiters(self, reason: str) -> None:
        for future in list(self._waiters):
            if not future.done():
                future.set_exception(ServerProcessError(reason))
        if self._save_future is not None and not self._save_future.done():
            self._save_future.set_exception(BackupRestoreError(reason))

    @asynccontextmanager
    async def save_session(
        self, timeout: float = 30, poll_interval: float = 1
    ) -> AsyncIterator[list[tuple[str, int]]]:
        async with self.protocol_lock:
            if not self.current():
                raise BackupRestoreError(
                    "Save session belongs to a replaced process generation."
                )
            future = asyncio.get_running_loop().create_future()
            self._save_future = future
            self._save_header = False
            self._save_entries = []
            self._save_bytes = 0
            self._protocol_task = asyncio.current_task()
            error: BaseException | None = None
            try:
                async with asyncio.timeout(timeout):
                    await self.server.send_command("save hold")
                    while not future.done():
                        if not self.current():
                            raise BackupRestoreError(
                                "Process generation changed during save session."
                            )
                        await self.server.send_command("save query")
                        await asyncio.wait({future}, timeout=poll_interval)
                    entries = future.result()
                yield entries
            except TimeoutError as failure:
                error = BackupRestoreError(
                    "Timed out waiting for complete save query response."
                )
                raise error from failure
            except BaseException as failure:
                error = failure
                raise
            finally:
                self._save_future = None
                self._save_entries = []
                self._save_bytes = 0
                self._protocol_task = None
                future.cancel()
                # Observe exceptions even if command delivery failed before awaiting.
                if not future.cancelled():
                    future.exception()
                if self.current() and self.process.returncode is None:

                    async def resume() -> None:
                        self._protocol_task = asyncio.current_task()
                        if not self.current():
                            raise BackupRestoreError(
                                "Refusing to resume saves on a replacement process."
                            )
                        async with asyncio.timeout(
                            self.server.settings.get(
                                "lifecycle.command_timeout_seconds", 5.0
                            )
                        ):
                            await self.server.send_command("save resume")

                    cleanup = asyncio.create_task(resume(), name="bds-save-resume")
                    try:
                        cancelled = False
                        while not cleanup.done():
                            try:
                                await asyncio.shield(cleanup)
                            except asyncio.CancelledError:
                                cancelled = True
                        cleanup.result()
                        if cancelled:
                            raise asyncio.CancelledError
                    except Exception as resume_error:
                        if error is not None:
                            error.add_note(
                                f"Resuming server saves also failed: {type(resume_error).__name__}"
                            )
                        else:
                            raise BackupRestoreError(
                                "World export completed, but server saves could not be resumed."
                            ) from resume_error

    async def stop(self) -> None:
        if self._stop_task is None or (
            self._stop_task.done() and self.process.returncode is None
        ):
            self._stop_task = asyncio.create_task(
                self._stop(), name=f"bds:{self.server.server_name}:stop-cleanup"
            )
            self._stop_task.add_done_callback(self._consume_failure)
        try:
            await asyncio.shield(self._stop_task)
        except Exception as error:
            self._fail(f"Stop cleanup failed: {type(error).__name__}")
            raise

    async def _stop(self) -> None:
        self.stop_requested = True
        readiness = self.workers.get("readiness")
        if readiness is not None:
            readiness.cancel()
        self.ready = False
        self.exit_reason = "requested"
        if self.failure is None:
            self.phase = "STOPPING"
        self.publish()
        self._effects.set()
        budget = self.server.settings.get("lifecycle.server_stop_timeout_seconds", 10.0)
        if self.process.returncode is None:
            try:
                async with asyncio.timeout(budget * 0.6):
                    await self.send("stop", shutdown=True, timeout=budget * 0.6)
                    await asyncio.shield(self.process.wait())
            except (Exception, asyncio.CancelledError) as error:
                if isinstance(error, asyncio.CancelledError):
                    raise
                if self.process.returncode is None:
                    self.exit_reason = "terminated"
                    with contextlib.suppress(ProcessLookupError):
                        self.process.terminate()
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(self.process.wait()), budget * 0.2
                        )
                    except TimeoutError:
                        self.exit_reason = "killed"
                        with contextlib.suppress(ProcessLookupError):
                            self.process.kill()
                        await asyncio.wait_for(
                            asyncio.shield(self.process.wait()), budget * 0.2
                        )
        await asyncio.wait_for(
            asyncio.shield(self.closed.wait()),
            self.server.settings.get("lifecycle.output_drain_timeout_seconds", 2.0) + 1,
        )

    async def _exited(self) -> None:
        try:
            await self.process.wait()
            drain = self.server.settings.get(
                "lifecycle.output_drain_timeout_seconds", 2.0
            )
            deadline = asyncio.get_running_loop().time() + drain
            for name in ("output", "log-writer"):
                task = self.workers[name]
                try:
                    await asyncio.wait_for(
                        asyncio.shield(task),
                        max(0.01, deadline - asyncio.get_running_loop().time()),
                    )
                except TimeoutError:
                    self.failure = (
                        self.failure or "Output task did not drain before deadline."
                    )
                    task.cancel()
            for xuid, name in list(self.players.items()):
                self.sequence += 1
                self._deltas.append(
                    {
                        "server_name": self.server.server_name,
                        "generation": self.generation,
                        "sequence": self.sequence,
                        "name": name,
                        "xuid": xuid,
                        "action": "disconnected",
                        "reason": "server_exit",
                    }
                )
            self.players.clear()
            self.sessions.clear()
            self.phase = "ERROR" if self.failure else "STOPPED"
            self.ready = False
            self.publish()
            self._fail_waiters("Process exited.")
            self._effects.set()
            # Deliver zero-player/status snapshots before releasing the generation.
            self._notifications_idle.clear()
            try:
                await asyncio.wait_for(
                    self._notifications_idle.wait(),
                    max(0.01, deadline - asyncio.get_running_loop().time()),
                )
            except TimeoutError:
                logger.warning("Process notifications did not drain before deadline")
            effects = [
                self.workers[name] for name in ("notifications", "bans", "readiness")
            ]
            for task in effects:
                task.cancel()
            await asyncio.wait(
                effects,
                timeout=max(0.01, deadline - asyncio.get_running_loop().time()),
            )
        except Exception as error:
            self.failure = f"Process finalization failed: {type(error).__name__}"
            self.phase = "ERROR"
            self.players.clear()
            self.sessions.clear()
            self.publish()
            self._fail_waiters(self.failure)
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            logger.exception("Process finalization failed")
        finally:
            self.on_exit(self)
            self.closed.set()
