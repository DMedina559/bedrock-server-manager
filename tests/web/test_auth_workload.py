"""Opt-in repeatable auth workload counters; never collect SQL text or credentials.

Run BSM_AUTH_BENCHMARK=1 pytest -s tests/web/test_auth_workload.py on a fixed
machine/database. Counters are for SQL statements, transactions, writes and elapsed
wall time separately; they are evidence, not fixed cross-platform latency budgets.
"""

import json
import math
import os
import statistics
import time

import pyotp
import pytest
from sqlalchemy import event

pytestmark = pytest.mark.skipif(
    os.environ.get("BSM_AUTH_BENCHMARK") != "1", reason="opt-in workload measurement"
)


async def test_auth_workloads(auth_client, app_context, websocket_client):
    import asyncio

    from bedrock_server_manager.web.auth import create_access_token

    token = await create_access_token(app_context, {"sub": "testuser"})
    headers = {"Authorization": f"Bearer {token}"}
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.get_user_by_username(
            session, "testuser"
        )
        owner_id = user.access_id
    # Prepare a real scoped credential and factor outside measured operations.
    from bedrock_server_manager.web.auth import _get_user_from_token
    from bedrock_server_manager.web.schemas.access import CreateIntegrationToken

    user = await _get_user_from_token(app_context, token)
    integration = await app_context.access_service.create_token(
        user, CreateIntegrationToken(name="Benchmark", permissions=["account:read"])
    )
    sample_count = max(
        1, min(int(os.environ.get("BSM_AUTH_BENCHMARK_SAMPLES", "3")), 5)
    )
    await app_context.settings.set("security.auth_peer_attempts", 1000)
    await app_context.settings.set("security.auth_account_attempts", 100)
    samples = []
    counts = {}
    engine = app_context._db.engine.sync_engine

    def statement(connection, cursor, statement, parameters, context, executemany):
        counts["statements"] += 1
        if statement.lstrip().split(None, 1)[0].upper() in {
            "INSERT",
            "UPDATE",
            "DELETE",
            "REPLACE",
        }:
            counts["writes"] += 1

    def begin(connection):
        counts["transactions"] += 1

    event.listen(engine, "before_cursor_execute", statement)
    event.listen(engine, "begin", begin)

    async def one_sample(name, action, status=200):
        counts.update(statements=0, writes=0, transactions=0)
        lock_before = app_context.storage.diagnostic_snapshot().total_lock_wait_ms
        started = time.perf_counter()
        response = await action()
        elapsed = (time.perf_counter() - started) * 1000
        if response is not None:
            assert response.status_code == status, response.text
        samples.append(
            {
                "workload": name,
                **counts,
                "elapsed_ms": round(elapsed, 3),
                "write_lock_wait_ms": round(
                    app_context.storage.diagnostic_snapshot().total_lock_wait_ms
                    - lock_before,
                    3,
                ),
            }
        )

        return response

    async def measure(name, action, status=200, *, repeat=None):
        response = None
        for _ in range(sample_count if repeat is None else repeat):
            response = await one_sample(name, action, status)
        return response

    try:
        await measure(
            "jwt_request", lambda: auth_client.get("/api/account", headers=headers)
        )
        await measure(
            "integration_request",
            lambda: auth_client.get(
                "/api/account", headers={"Authorization": f"Bearer {integration.token}"}
            ),
        )
        await measure(
            "login_success",
            lambda: auth_client.post(
                "/auth/token", data={"username": "testuser", "password": "testpassword"}
            ),
        )
        await measure(
            "login_failed",
            lambda: auth_client.post(
                "/auth/token", data={"username": "testuser", "password": "wrong"}
            ),
            401,
        )
        enrolled = await app_context.session_service.enrollment(owner_id, "testuser")
        confirmed = await app_context.session_service.confirm_enrollment(
            owner_id, pyotp.TOTP(enrolled["secret"]).now()
        )
        await measure(
            "login_mfa_challenge",
            lambda: auth_client.post(
                "/auth/token", data={"username": "testuser", "password": "testpassword"}
            ),
            401,
        )
        credentials = {"username": "testuser", "password": "testpassword"}
        future_code = pyotp.TOTP(enrolled["secret"]).at(
            (int(time.time()) // 30 + 1) * 30
        )
        await measure(
            "login_mfa_totp",
            lambda: auth_client.post(
                "/auth/token", data={**credentials, "otp": future_code}
            ),
            repeat=1,
        )
        codes = iter(confirmed["recovery_codes"][1:])
        await measure(
            "login_mfa_recovery",
            lambda: auth_client.post(
                "/auth/token", data={**credentials, "otp": next(codes)}
            ),
        )
        remembered = await measure(
            "remembered_device_create",
            lambda: auth_client.post(
                "/auth/token",
                data={
                    **credentials,
                    "otp": confirmed["recovery_codes"][0],
                    "remember_device": "true",
                },
            ),
            repeat=1,
        )
        proof = remembered.json()["trusted_device_token"]
        trusted_headers = {
            "Authorization": "Bearer " + remembered.json()["access_token"],
            "X-BSM-Trusted-Device-Token": proof,
        }
        await measure(
            "remembered_login",
            lambda: auth_client.post(
                "/auth/token", data={**credentials, "trusted_device_token": proof}
            ),
        )
        await measure(
            "remembered_password_step_up",
            lambda: auth_client.post(
                "/api/account/security/verify",
                headers=trusted_headers,
                json={"password": "testpassword"},
            ),
        )
        await measure(
            "remembered_invalid",
            lambda: auth_client.post(
                "/auth/token",
                data={**credentials, "trusted_device_token": proof + "invalid"},
            ),
            401,
        )
        # Obtain a new family after enrollment revoked earlier sessions.
        token = await create_access_token(app_context, {"sub": "testuser"})
        async with websocket_client() as socket:
            await socket.send(json.dumps({"action": "authenticate", "token": token}))
            assert json.loads(await socket.recv())["status"] == "success"
            client_id = next(iter(app_context.connection_manager.active_connections))

            async def frame():
                await socket.send(
                    json.dumps({"action": "subscribe", "topic": "access-policy"})
                )
                assert json.loads(await socket.recv())["status"] == "success"

            await measure("websocket_receive_reply", frame, repeat=1)

            async def delivery():
                await app_context.connection_manager.send_to_client(
                    {"benchmark": True}, client_id
                )
                assert json.loads(await socket.recv())["benchmark"] is True

            await measure("websocket_delivery", delivery, repeat=1)

        async def concurrent():
            responses = await asyncio.gather(
                *[
                    auth_client.get(
                        "/api/account", headers={"Authorization": f"Bearer {token}"}
                    )
                    for _ in range(8)
                ]
            )
            assert all(response.status_code == 200 for response in responses)

        await measure("jwt_concurrent_8", concurrent)

        async def mixed():
            responses = await asyncio.gather(
                auth_client.get("/api/account", headers=trusted_headers),
                auth_client.post(
                    "/auth/token", data={**credentials, "trusted_device_token": proof}
                ),
                auth_client.post(
                    "/api/account/security/verify",
                    headers=trusted_headers,
                    json={"password": "testpassword"},
                ),
            )
            assert all(response.status_code == 200 for response in responses)

        await measure("mixed_login_and_step_up", mixed)
        from sqlalchemy import update

        from bedrock_server_manager.db.models import TrustedDevice

        async with app_context.storage.transaction() as session:
            await session.execute(
                update(TrustedDevice)
                .where(TrustedDevice.owner_id == owner_id)
                .values(expires_at=int(time.time()) - 1)
            )
        await measure(
            "remembered_expired",
            lambda: auth_client.post(
                "/auth/token", data={**credentials, "trusted_device_token": proof}
            ),
            401,
        )
        async with app_context.storage.transaction() as session:
            await session.execute(
                update(TrustedDevice)
                .where(TrustedDevice.owner_id == owner_id)
                .values(expires_at=int(time.time()) + 86400)
            )
        await app_context.trusted_device_service.revoke(owner_id)
        await measure(
            "remembered_revoked",
            lambda: auth_client.post(
                "/auth/token", data={**credentials, "trusted_device_token": proof}
            ),
            401,
        )

    finally:
        event.remove(engine, "before_cursor_execute", statement)
        event.remove(engine, "begin", begin)
    print("AUTH_WORKLOAD " + json.dumps(samples, sort_keys=True))

    summaries = []
    for name in sorted({item["workload"] for item in samples}):
        timings = sorted(
            item["elapsed_ms"] for item in samples if item["workload"] == name
        )
        summaries.append(
            {
                "workload": name,
                "samples": len(timings),
                "median_ms": round(statistics.median(timings), 3),
                "p95_ms": timings[math.ceil(len(timings) * 0.95) - 1],
            }
        )
    print("AUTH_WORKLOAD_SUMMARY " + json.dumps(summaries, sort_keys=True))
