# plugins/benchmark_plugin.py
"""
Benchmark Plugin for Bedrock Server Manager (BSM).

Tracks application performance metrics including process CPU %, RSS memory, thread count,
active asyncio task count, event loop lag, system metrics (CPU, RAM, Network & Disk I/O),
and dynamic Bedrock server PIDs resource usage at configurable periodic intervals (default 3 seconds).
"""

import asyncio
import os
import time
from typing import Any, Dict, Optional

try:
    import psutil  # type: ignore

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_AVAILABLE = False

from bedrock_server_manager import PluginBase, app_event, task_loop


class BenchmarkPlugin(PluginBase):
    """
    Custom benchmark plugin that measures performance metrics of BSM and active servers.
    """

    name = "Benchmark Plugin"
    version = "1.0.0"
    author = "BSM Team"
    description = (
        "Tracks real-time process CPU, RAM, threads, asyncio tasks, loop lag, system I/O, "
        "and dynamic Bedrock server process PIDs at regular interval."
    )

    def __init__(self, plugin_name: str, api: Any, logger: Any):
        super().__init__(plugin_name, api, logger)
        self._main_process: Optional[Any] = None
        if PSUTIL_AVAILABLE:
            try:
                self._main_process = psutil.Process(os.getpid())
                # Warm up cpu_percent calculation
                self._main_process.cpu_percent(interval=None)
            except Exception:
                self._main_process = None

        self._last_net_io: Optional[Any] = None
        self._last_disk_io: Optional[Any] = None
        self._last_io_time: float = time.monotonic()
        self._tracked_servers: Dict[str, Dict[str, Any]] = {}

        if PSUTIL_AVAILABLE:
            try:
                self._last_net_io = psutil.net_io_counters()
                self._last_disk_io = psutil.disk_io_counters()
            except Exception:
                pass

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs: Any) -> None:
        """
        Hook called when plugin is loaded.
        """
        self.logger.info(
            f"'{self.name}' v{self.version} loaded. PSUTIL available: {PSUTIL_AVAILABLE}."
        )

    @app_event("after_server_start")
    async def on_server_started(self, **kwargs: Any) -> None:
        """
        Hook triggered when a server starts. Tracks the server's PID if available.
        """
        server_name = str(kwargs.get("server_name", "unknown"))
        result = kwargs.get("result", {})
        pid = kwargs.get("pid") or result.get("pid")

        if not pid and server_name and hasattr(self.api, "get_bedrock_process_info"):
            try:
                info_res = await self.api.get_bedrock_process_info(server_name)
                if isinstance(info_res, dict) and info_res.get("status") == "success":
                    p_info = info_res.get("process_info")
                    if isinstance(p_info, dict):
                        pid = p_info.get("pid")
            except Exception:
                pass

        if pid:
            self.logger.info(
                f"Benchmark plugin notified: Server '{server_name}' started (PID: {pid})."
            )
        else:
            self.logger.info(
                f"Benchmark plugin notified: Server '{server_name}' started."
            )

        if server_name:
            self._tracked_servers[server_name] = {"pid": pid, "status": "running"}

    @app_event("after_server_stop")
    @app_event("on_server_stop")
    async def on_server_stopped(self, **kwargs: Any) -> None:
        """
        Hook triggered when a server stops. Removes or updates tracking for the server.
        """
        server_name = str(kwargs.get("server_name", "unknown"))
        self.logger.info(f"Benchmark plugin notified: Server '{server_name}' stopped.")
        if server_name in self._tracked_servers:
            self._tracked_servers.pop(server_name, None)

    async def _measure_loop_lag(self) -> float:
        """
        Measures asyncio event loop latency in milliseconds.
        """
        start = time.perf_counter()
        await asyncio.sleep(0)
        elapsed = (time.perf_counter() - start) * 1000.0
        return elapsed

    @task_loop(3.0)
    async def benchmark_loop(self) -> None:
        """
        Periodic benchmarking loop executed every 3 seconds (or custom configured interval).
        """
        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil is not installed. Benchmark metrics limited.")
            return

        now = time.monotonic()
        time_delta = max(now - self._last_io_time, 0.001)
        self._last_io_time = now

        # 1. Main Process Metrics
        app_cpu = 0.0
        app_ram_mb = 0.0
        thread_count = 0
        if self._main_process:
            try:
                app_cpu = self._main_process.cpu_percent(interval=None)
                mem_info = self._main_process.memory_info()
                app_ram_mb = mem_info.rss / (1024 * 1024)
                thread_count = self._main_process.num_threads()
            except Exception as err:
                self.logger.debug(f"Error fetching main process info: {err}")

        # Asyncio tasks & event loop lag
        task_count = len(asyncio.all_tasks())
        loop_lag_ms = await self._measure_loop_lag()

        # 2. System Metrics
        sys_cpu = psutil.cpu_percent(interval=None)
        sys_ram = psutil.virtual_memory()
        sys_ram_mb = sys_ram.used / (1024 * 1024)
        sys_ram_pct = sys_ram.percent

        # Net I/O Delta
        net_tx_kbps = 0.0
        net_rx_kbps = 0.0
        try:
            net_io = psutil.net_io_counters()
            if self._last_net_io and net_io:
                tx_diff = net_io.bytes_sent - self._last_net_io.bytes_sent
                rx_diff = net_io.bytes_recv - self._last_net_io.bytes_recv
                net_tx_kbps = (tx_diff / 1024.0) / time_delta
                net_rx_kbps = (rx_diff / 1024.0) / time_delta
            self._last_net_io = net_io
        except Exception:
            pass

        # Disk I/O Delta
        disk_read_kbps = 0.0
        disk_write_kbps = 0.0
        try:
            disk_io = psutil.disk_io_counters()
            if self._last_disk_io and disk_io:
                r_diff = disk_io.read_bytes - self._last_disk_io.read_bytes
                w_diff = disk_io.write_bytes - self._last_disk_io.write_bytes
                disk_read_kbps = (r_diff / 1024.0) / time_delta
                disk_write_kbps = (w_diff / 1024.0) / time_delta
            self._last_disk_io = disk_io
        except Exception:
            pass

        # 3. Dynamic Bedrock Server PIDs Metrics
        server_metrics = []
        active_servers_list = []
        try:
            if hasattr(self.api, "get_all_servers_data"):
                res = await self.api.get_all_servers_data()
            elif hasattr(self.api, "list_servers"):
                res = await self.api.list_servers()
            else:
                res = None

            if isinstance(res, dict) and res.get("status") == "success":
                active_servers_list = res.get("servers", [])
            elif isinstance(res, list):
                active_servers_list = res
        except Exception as err:
            self.logger.debug(f"Error querying active servers: {err}")

        # Merge tracked servers and active servers
        server_pids_to_check: Dict[str, Optional[int]] = {}
        for s in active_servers_list:
            if isinstance(s, dict):
                s_name = s.get("name") or s.get("server_name")
                s_pid = s.get("pid")
                s_status = s.get("status")
                if s_name and (s_status == "running" or s_pid):
                    server_pids_to_check[s_name] = s_pid

        for s_name, s_info in self._tracked_servers.items():
            if s_name not in server_pids_to_check:
                server_pids_to_check[s_name] = s_info.get("pid")

        for s_name, fallback_pid in server_pids_to_check.items():
            # Attempt to query via BSM system API 'get_bedrock_process_info'
            p_info = None
            try:
                if hasattr(self.api, "get_bedrock_process_info"):
                    res = await self.api.get_bedrock_process_info(s_name)
                    if isinstance(res, dict) and res.get("status") == "success":
                        p_info = res.get("process_info")
            except Exception as err:
                self.logger.debug(
                    f"API query for process info '{s_name}' failed: {err}"
                )

            if p_info and isinstance(p_info, dict):
                pid = p_info.get("pid")
                s_cpu = p_info.get("cpu_percent", 0.0)
                s_ram = p_info.get("memory_mb", 0.0)
                server_metrics.append(
                    f"{s_name}[PID {pid}]: CPU {s_cpu:.1f}%, RAM {s_ram:.1f}MB"
                )
            else:
                pid = fallback_pid
                if not pid:
                    server_metrics.append(f"{s_name}(no-pid)")
                    continue
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running():
                        s_cpu = proc.cpu_percent(interval=None)
                        s_ram = proc.memory_info().rss / (1024 * 1024)
                        server_metrics.append(
                            f"{s_name}[PID {pid}]: CPU {s_cpu:.1f}%, RAM {s_ram:.1f}MB"
                        )
                    else:
                        server_metrics.append(f"{s_name}[PID {pid}]: stopped")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    server_metrics.append(f"{s_name}[PID {pid}]: inactive")
                except Exception as err:
                    server_metrics.append(f"{s_name}[PID {pid}]: err({err})")

        servers_str = ", ".join(server_metrics) if server_metrics else "none"

        log_msg = (
            f"[Benchmark] App CPU: {app_cpu:.1f}% | RAM: {app_ram_mb:.1f}MB | "
            f"Threads: {thread_count} | Tasks: {task_count} | Loop Lag: {loop_lag_ms:.2f}ms | "
            f"Sys CPU: {sys_cpu:.1f}% | Sys RAM: {sys_ram_mb:.1f}MB ({sys_ram_pct:.1f}%) | "
            f"Net: ^{net_tx_kbps:.1f}KB/s v{net_rx_kbps:.1f}KB/s | "
            f"Disk: R {disk_read_kbps:.1f}KB/s W {disk_write_kbps:.1f}KB/s | "
            f"Servers: [{servers_str}]"
        )
        self.logger.info(log_msg)

    @app_event("on_unload")
    async def plugin_unloaded(self, **kwargs: Any) -> None:
        """
        Hook called when plugin is unloaded.
        """
        self.logger.info(f"'{self.name}' v{self.version} unloaded.")
