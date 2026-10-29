"""Transient history writes retain bounded, idempotent background ownership."""

import asyncio
import sqlite3
import time

import pytest
from sqlalchemy.exc import OperationalError

from bedrock_server_manager.diagnostics import history as module
from bedrock_server_manager.diagnostics.models import DiagnosticOptions
from bedrock_server_manager.diagnostics.service import Diagnostics


@pytest.mark.parametrize("after_commit", [False, True])
async def test_deadline_retry_preserves_one_history_record(
    db, monkeypatch, after_commit
):
    store = module.DiagnosticHistoryStore(db, DiagnosticOptions())
    service = Diagnostics(store, store.options)
    original = store._write
    attempts = 0

    async def transient(record):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            if after_commit:
                await original(record)
            raise TimeoutError
        await original(record)

    monkeypatch.setattr(store, "_write", transient)
    store.start()
    try:
        service.record("storage", "retry-probe", started=time.monotonic())
        await asyncio.wait_for(store.queue.join(), 5)
        retained = await store.read()
        assert attempts == 2
        assert len(retained.records) == 1
        assert store.dropped == 0 and store.write_failures == 1
        assert store.last_error_type is None
    finally:
        await store.close()


async def test_transient_failure_has_finite_attempts_and_one_drop(db, monkeypatch):
    store = module.DiagnosticHistoryStore(db, DiagnosticOptions())
    service = Diagnostics(store, store.options)
    calls = 0

    async def fail(record):
        nonlocal calls
        calls += 1
        raise TimeoutError

    monkeypatch.setattr(store, "_write", fail)
    store.start()
    try:
        service.record("storage", "bounded-retry", started=time.monotonic())
        await asyncio.wait_for(store.queue.join(), 5)
        assert calls == 3 and store.write_failures == 3
        assert store.dropped == 1 and store.last_error_type == "TimeoutError"
    finally:
        await store.close()


async def test_shutdown_during_retry_counts_inflight_and_queued_records(
    db, monkeypatch
):
    store = module.DiagnosticHistoryStore(db, DiagnosticOptions(queue_limit=2))
    service = Diagnostics(store, store.options)
    entered = asyncio.Event()

    async def fail(record):
        entered.set()
        raise TimeoutError

    monkeypatch.setattr(store, "_write", fail)
    monkeypatch.setattr(module, "RETRY_DELAYS", (10, 10))
    store.start()
    service.record("storage", "first", started=time.monotonic())
    service.record("storage", "second", started=time.monotonic())
    await entered.wait()
    await store.close()
    assert store.dropped == 2
    assert store.queue.empty()
    await store.queue.join()


def test_retry_classification_distinguishes_locks_from_invalid_sql():
    busy = sqlite3.OperationalError("busy")
    busy.sqlite_errorcode = sqlite3.SQLITE_BUSY
    assert module.retryable_write(OperationalError("query", {}, busy))
    invalid = sqlite3.OperationalError("no such table")
    invalid.sqlite_errorcode = sqlite3.SQLITE_ERROR
    assert not module.retryable_write(OperationalError("query", {}, invalid))
    assert not module.retryable_write(RuntimeError("invalid record"))


async def test_actual_write_deadline_retries_after_cancelling_attempt(db, monkeypatch):
    store = module.DiagnosticHistoryStore(db, DiagnosticOptions())
    service = Diagnostics(store, store.options)
    original = store._write
    cancelled = asyncio.Event()
    attempts = 0

    async def blocked(record):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            try:
                await asyncio.Event().wait()
            finally:
                monkeypatch.setattr(module, "WRITE_TIMEOUT_SECONDS", 2.0)
                cancelled.set()
        else:
            await original(record)

    monkeypatch.setattr(module, "WRITE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(store, "_write", blocked)
    store.start()
    try:
        service.record("storage", "deadline", started=time.monotonic())
        await asyncio.wait_for(store.queue.join(), 5)
        assert cancelled.is_set() and attempts == 2
        assert store.dropped == 0
        assert len((await store.read()).records) == 1
    finally:
        await store.close()
