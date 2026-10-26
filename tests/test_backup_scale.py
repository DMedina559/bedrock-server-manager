"""Repeatable archive scale probe; optional environment sizes avoid CI timing gates."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import psutil

from bedrock_server_manager.utils.threads import run_in_thread


async def test_many_file_backup_keeps_event_loop_responsive(populated_server):
    server = populated_server
    size = int(os.environ.get("BSM_BACKUP_BENCHMARK_BYTES", 4 * 1048576))
    count = int(os.environ.get("BSM_BACKUP_BENCHMARK_FILES", 128))
    assert 1048576 <= size <= 1024**3 and 1 <= count <= 10000
    root = Path(server.paths.server_dir)
    world = root / "worlds" / await server.get_world_name()
    payload = world / "acceptance-probe"

    def populate():
        payload.mkdir()
        block = os.urandom(1048576)
        with (payload / "large.bin").open("wb") as stream:
            remaining = size
            while remaining:
                chunk = block[: min(remaining, len(block))]
                stream.write(chunk)
                remaining -= len(chunk)
        for index in range(count):
            (payload / f"record-{index:05d}.bin").write_bytes(block[:4096])

    await run_in_thread(populate)
    started, finished = asyncio.Event(), asyncio.Event()
    ticks, rss, extra_disk = [], [], []
    process = psutil.Process() if os.name == "nt" else None

    def memory_usage():
        if os.name == "posix":
            import resource

            value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return value if sys.platform == "darwin" else value * 1024
        assert process is not None
        return process.memory_info().rss

    backup_root = Path(server.backups._directory())

    def logical_bytes():
        total = 0
        for parent in (root, backup_root):
            # Capture cleanup can remove a directory during sampling. os.walk
            # skips vanished directories, including on Python 3.11/Windows.
            for directory, _directories, files in os.walk(parent):
                for filename in files:
                    path = Path(directory) / filename
                    try:
                        if not path.is_symlink():
                            total += path.stat().st_size
                    except FileNotFoundError:
                        pass
        return total

    baseline = await run_in_thread(logical_bytes)

    async def sample():
        while not finished.is_set():
            ticks.append(time.perf_counter())
            rss.append(memory_usage())
            extra_disk.append(max(0, await run_in_thread(logical_bytes) - baseline))
            await asyncio.sleep(0.01)

    async def progress(_message):
        started.set()

    async def foreground():
        begin = time.perf_counter()
        async with server.operation_lock:
            return time.perf_counter() - begin

    sampler = asyncio.create_task(sample())
    try:
        begin = time.perf_counter()
        capture = asyncio.create_task(server.backups.create_snapshot(progress=progress))
        await started.wait()
        interactive = asyncio.create_task(foreground())
        snapshot = await capture
        capture_seconds = time.perf_counter() - begin
        foreground_seconds = await interactive
        begin = time.perf_counter()
        plan = await server.backups.plan_restore(
            snapshot.backup_id, ["world"], dry_run=True
        )
        dry_run_seconds = time.perf_counter() - begin
    finally:
        finished.set()
        await sampler
    assert plan.sufficient_space and plan.checked_files >= count + 1
    assert len(ticks) >= 2
    print(
        "BACKUP_SCALE "
        + json.dumps(
            {
                "payload_bytes": size,
                "small_files": count,
                "capture_seconds": round(capture_seconds, 3),
                "dry_run_seconds": round(dry_run_seconds, 3),
                "foreground_wait_seconds": round(foreground_seconds, 3),
                "peak_process_rss_bytes": max(rss),
                "peak_extra_logical_bytes": max(extra_disk),
                "max_sampling_gap_seconds": round(
                    max(b - a for a, b in zip(ticks, ticks[1:])), 3
                ),
            }
        )
    )
