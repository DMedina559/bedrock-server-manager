"""One lifecycle-owned sampler shared by HTTP and WebSocket consumers."""

import asyncio
import logging
import os
import time
from collections import deque
from typing import TYPE_CHECKING, Any

import psutil

from ..api.models.metrics import (
    GetApplicationMetricsResponse,
    MetricsSample,
    ServerMetrics,
)
from ..diagnostics.models import MetricsDiagnostics
from ..logging import RepeatedFailureReporter
from ..state_revision import revision_clock

if TYPE_CHECKING:
    from ..context import AppContext

logger = logging.getLogger(__name__)


class MetricsService:
    history_limit = 180

    def __init__(self, app_context: "AppContext") -> None:
        self.context = app_context
        self._history: deque[MetricsSample] = deque(maxlen=self.history_limit)
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._snapshot_lock = asyncio.Lock()
        self._process: Any = None
        self._net: Any = None
        self._disk: Any = None
        self._cpu: Any = None
        self._time: float | None = None
        self._failures = RepeatedFailureReporter(logger)
        self.telemetry = MetricsDiagnostics()
        self._last_success_monotonic: float | None = None

    @property
    def interval_seconds(self) -> float:
        return float(
            self.context.settings.get("monitoring.app_metrics_interval_sec", 3)
        )

    def _collect(self) -> dict[str, Any]:
        """OS reads run outside the event loop; retain CPU and rate baselines."""
        now = time.monotonic()
        elapsed = now - self._time if self._time is not None else None
        values: dict[str, Any] = {}
        try:
            if self._process is None:
                self._process = psutil.Process(os.getpid())
                self._process.cpu_percent(None)
            else:
                values["app_cpu_percent"] = max(0.0, self._process.cpu_percent(None))
            with self._process.oneshot():
                values.update(
                    app_ram_mb=self._process.memory_info().rss / 1024**2,
                    thread_count=self._process.num_threads(),
                    uptime_seconds=max(0.0, time.time() - self._process.create_time()),
                )
        except (psutil.Error, OSError):
            self._process = None
        try:
            memory = psutil.virtual_memory()
            values.update(
                sys_ram_mb=memory.used / 1024**2,
                sys_ram_total_mb=memory.total / 1024**2,
                sys_ram_percent=memory.percent,
            )
            cpu = psutil.cpu_times()
            if self._cpu is not None:
                total = (
                    sum(cpu) - getattr(cpu, "guest", 0) - getattr(cpu, "guest_nice", 0)
                ) - (
                    sum(self._cpu)
                    - getattr(self._cpu, "guest", 0)
                    - getattr(self._cpu, "guest_nice", 0)
                )
                idle = (cpu.idle + getattr(cpu, "iowait", 0)) - (
                    self._cpu.idle + getattr(self._cpu, "iowait", 0)
                )
                if total > 0:
                    values["sys_cpu_percent"] = max(
                        0.0, min(100.0, 100 * (total - idle) / total)
                    )
            self._cpu = cpu
        except (psutil.Error, OSError):
            self._cpu = None
        for attribute, read, fields in (
            (
                "_net",
                psutil.net_io_counters,
                (("net_tx_kib_s", "bytes_sent"), ("net_rx_kib_s", "bytes_recv")),
            ),
            (
                "_disk",
                psutil.disk_io_counters,
                (
                    ("disk_read_kib_s", "read_bytes"),
                    ("disk_write_kib_s", "write_bytes"),
                ),
            ),
        ):
            try:
                counters = read()
                previous = getattr(self, attribute)
                if (
                    counters is not None
                    and previous is not None
                    and elapsed is not None
                    and elapsed > 0
                ):
                    for field, counter in fields:
                        delta = getattr(counters, counter) - getattr(previous, counter)
                        if delta >= 0:
                            values[field] = delta / 1024 / elapsed
                setattr(self, attribute, counters)
            except (psutil.Error, OSError):
                setattr(self, attribute, None)
        self._time = now
        return values

    async def sample(self, lag_ms: float = 0.0) -> MetricsSample:
        async with self._lock:
            started = time.monotonic()
            stats = self.telemetry
            stats.attempts += 1
            try:
                sample = await self._sample(lag_ms)
                stats.successes += 1
                stats.last_error_type = None
                stats.last_sample_at = sample.timestamp
                stats.interval_seconds = self.interval_seconds
                stats.warming_up = stats.successes < 2
                stats.unavailable_measurements = [
                    name
                    for name in (
                        "app_cpu_percent",
                        "app_ram_mb",
                        "thread_count",
                        "uptime_seconds",
                        "sys_cpu_percent",
                        "sys_ram_mb",
                        "sys_ram_total_mb",
                        "sys_ram_percent",
                        "net_tx_kib_s",
                        "net_rx_kib_s",
                        "disk_read_kib_s",
                        "disk_write_kib_s",
                    )
                    if getattr(sample, name) is None
                ]
                if self._last_success_monotonic is not None:
                    stats.missed_intervals += max(
                        0,
                        int(
                            (started - self._last_success_monotonic)
                            / self.interval_seconds
                        )
                        - 1,
                    )
                self._last_success_monotonic = started
                return sample
            except Exception as error:
                stats.failures += 1
                stats.last_error_type = type(error).__name__
                if self.context._diagnostics is not None:
                    self.context._diagnostics.record(
                        "metrics", "sample", started=started, error=error
                    )
                raise
            finally:
                stats.last_duration_ms = max(0, (time.monotonic() - started) * 1000)

    def diagnostic_snapshot(self) -> MetricsDiagnostics:
        """Expose sampler metadata without triggering resource reads."""
        result = self.telemetry.model_copy(deep=True)
        if result.last_sample_at is not None:
            result.sample_age_seconds = max(0, time.time() - result.last_sample_at)
        result.interval_seconds = self.interval_seconds
        return result

    async def _sample(self, lag_ms: float = 0.0) -> MetricsSample:
        stamp = revision_clock.capture()
        task_count = len(asyncio.all_tasks())
        values = await asyncio.to_thread(self._collect)
        servers = []
        for name in self.context.state.servers.servers:
            # Lifecycle/startup monitoring owns process discovery. Sampling
            # must not repeatedly probe PID files for known stopped servers.
            if not self.context.state.runtime.get_server_runtime(name).running:
                continue
            try:
                info = await self.context.get_server(name).get_process_info()
                servers.append(
                    ServerMetrics.model_validate(
                        {
                            "server_name": name,
                            **{
                                key: value
                                for key, value in (info or {}).items()
                                if key in {"pid", "cpu_percent", "memory_mb"}
                            },
                        }
                    )
                )
            except Exception:
                logger.debug(
                    "Process metrics unavailable for server '%s'.",
                    name,
                    exc_info=True,
                )
                servers.append(ServerMetrics(server_name=name))
        sample = MetricsSample(
            timestamp=time.time(),
            asyncio_task_count=task_count,
            background_task_count=self.context.task_manager.active_task_count,
            loop_lag_ms=max(0.0, lag_ms),
            servers=servers,
            **values,
            **stamp,
        )
        self._history.append(sample)
        return sample.model_copy(deep=True)

    async def snapshot(self) -> GetApplicationMetricsResponse:
        async with self._snapshot_lock:
            if not self._history:
                await self.sample()
        latest = self._history[-1]
        return GetApplicationMetricsResponse(
            latest=latest.model_copy(deep=True),
            history=[sample.model_copy(deep=True) for sample in self._history],
            interval_seconds=self.interval_seconds,
            history_limit=self.history_limit,
            epoch=latest.epoch,
            revision=latest.revision,
        )

    async def _run(self) -> None:
        deadline = asyncio.get_running_loop().time()
        while True:
            try:
                sample = await self.sample(
                    (asyncio.get_running_loop().time() - deadline) * 1000
                )
                await self.context.connection_manager.broadcast_to_topic(
                    "application-metrics",
                    {
                        "type": "resource_update",
                        "topic": "application-metrics",
                        "data": sample.model_dump(mode="json"),
                    },
                )
                self._failures.recover("application metrics")
            except Exception as error:
                self._failures.report(
                    "application metrics",
                    "Application metrics unavailable (%s): %s; retrying.",
                    error,
                )
            deadline = asyncio.get_running_loop().time() + self.interval_seconds
            await asyncio.sleep(self.interval_seconds)

    def check_health(self) -> bool:
        """Require a live sampler and a recent successful observation."""
        return bool(
            self._task is not None
            and not self._task.done()
            and self._history
            and time.time() - self._history[-1].timestamp <= self.interval_seconds * 3
        )

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="application-metrics")

    async def shutdown(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
