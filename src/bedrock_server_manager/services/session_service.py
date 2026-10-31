"""Persisted login families, bounded authentication and factor verification."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import io
import os
import secrets
import time
from pathlib import Path
from uuid import uuid4

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError

from ..db.models import (
    AccountSecurity,
    AuthSecurityEvent,
    AuthThrottle,
    IntegrationToken,
    LoginSession,
    User,
)
from ..utils.threads import run_in_thread


class SessionService:
    def __init__(self, context):
        self.context = context

    def idle_seconds(self):
        return max(
            300,
            min(
                int(self.context.settings.get("security.session_idle_hours", 24))
                * 3600,
                28 * 86400,
            ),
        )

    async def event(self, user_id, action, **details):
        async with self.context.storage.transaction() as session:
            user = await session.get(User, user_id)
            if user is not None:
                self.add_event(session, user.access_id, action, details)

    @staticmethod
    def add_event(session, owner_id, action, details=None):
        session.add(
            AuthSecurityEvent(
                id=uuid4().hex,
                owner_id=owner_id,
                action=action,
                timestamp=int(time.time()),
                details=details or {},
            )
        )

    async def throttle(self, username, peer="", operation="login"):
        # Consume IP first: arbitrary usernames cannot create unbounded rows per peer.
        for value, limit in (
            (f"peer:{peer}", 60),
            (f"{operation}:{username.casefold()}", 10),
        ):
            key = hashlib.sha256(value.encode()).hexdigest()
            now = int(time.time())
            window = now // 300
            for retry in range(2):
                try:
                    async with self.context.storage.transaction() as session:
                        await session.execute(
                            delete(AuthThrottle).where(
                                AuthThrottle.window < window - 288
                            )
                        )
                        result = await session.execute(
                            update(AuthThrottle)
                            .where(AuthThrottle.key == key)
                            .values(
                                window=window,
                                attempts=case(
                                    (
                                        AuthThrottle.window == window,
                                        AuthThrottle.attempts + 1,
                                    ),
                                    else_=1,
                                ),
                            )
                        )
                        if result.rowcount == 0:
                            session.add(
                                AuthThrottle(key=key, window=window, attempts=1)
                            )
                            await session.flush()
                        attempts = await session.scalar(
                            select(AuthThrottle.attempts).where(AuthThrottle.key == key)
                        )
                    break
                except IntegrityError:
                    if retry:
                        raise
            if attempts > limit:
                raise HTTPException(
                    429,
                    "Too many authentication attempts. Try again shortly.",
                    headers={"Retry-After": str(300 - now % 300)},
                )

    async def authentication_succeeded(self, username, operation="login"):
        key = hashlib.sha256(f"{operation}:{username.casefold()}".encode()).hexdigest()
        async with self.context.storage.transaction() as session:
            await session.execute(delete(AuthThrottle).where(AuthThrottle.key == key))

    async def create(self, owner_id, expires_at, expected_revision=None):
        now = int(time.time())
        maximum = (
            max(
                1,
                min(
                    int(self.context.settings.get("security.session_max_days", 28)), 90
                ),
            )
            * 86400
        )
        async with self.context.storage.transaction() as session:
            current = await session.scalar(
                select(User).where(User.access_id == owner_id).with_for_update()
            )
            if (
                current is None
                or not current.is_active
                or (
                    expected_revision is not None
                    and current.auth_revision != expected_revision
                )
            ):
                raise HTTPException(401, "Account credentials changed; sign in again")
            await session.execute(
                delete(LoginSession).where(LoginSession.expires_at < now - 90 * 86400)
            )
            count = await session.scalar(
                select(func.count())
                .select_from(LoginSession)
                .where(
                    LoginSession.owner_id == owner_id,
                    LoginSession.revoked_at.is_(None),
                    LoginSession.expires_at > now,
                )
            )
            if count >= 100:
                raise HTTPException(
                    409, "Sign out an unused session before signing in again"
                )
            record = LoginSession(
                id=uuid4().hex,
                owner_id=owner_id,
                name="API login",
                user_agent="",
                ip_address="",
                created_at=now,
                last_seen_at=now,
                expires_at=min(expires_at, now + maximum),
                verified_at=now,
            )
            session.add(record)
            self.add_event(session, owner_id, "login", {"session_id": record.id})
            return record.id, record.expires_at

    async def validate(self, identifier, owner_id=None, *, touch=True):
        if not isinstance(identifier, str) or len(identifier) != 32:
            return None
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            record = await session.get(LoginSession, identifier)
            if (
                record is None
                or record.revoked_at is not None
                or record.expires_at <= now
            ):
                return None
            if owner_id is not None and record.owner_id != owner_id:
                return None
            if record.last_seen_at + self.idle_seconds() <= now:
                return None
            if touch and record.last_seen_at < now - 60:
                await session.execute(
                    update(LoginSession)
                    .where(
                        LoginSession.id == identifier,
                        LoginSession.last_seen_at < now - 60,
                    )
                    .values(last_seen_at=now)
                )
            return record

    async def annotate(self, identifier, request):
        agent = request.headers.get("user-agent", "")[:512]
        name = request.headers.get("x-bsm-client", "")[:100].strip()
        if not name:
            browser = next(
                (
                    label
                    for marker, label in (
                        ("Edg/", "Edge"),
                        ("Firefox/", "Firefox"),
                        ("Chrome/", "Chrome"),
                        ("Safari/", "Safari"),
                    )
                    if marker in agent
                ),
                "API client",
            )
            platform = next(
                (
                    label
                    for marker, label in (
                        ("Android", "Android"),
                        ("iPhone", "iOS"),
                        ("Windows", "Windows"),
                        ("Macintosh", "macOS"),
                        ("Linux", "Linux"),
                    )
                    if marker in agent
                ),
                "",
            )
            name = " · ".join(filter(None, (browser, platform)))
        async with self.context.storage.transaction() as session:
            await session.execute(
                update(LoginSession)
                .where(LoginSession.id == identifier)
                .values(
                    name=name,
                    user_agent=agent,
                    ip_address=(request.client.host if request.client else "")[:64],
                )
            )

    async def require_recent(self, user, identifier):
        record = await self.validate(identifier, touch=False)
        if record is None:
            raise HTTPException(401, "Sign in again to manage security settings")
        async with self.context.storage.transaction() as session:
            owner = await session.get(User, user.id)
            if owner is None or owner.access_id != record.owner_id:
                raise HTTPException(403, "Session owner mismatch")
        if record.verified_at < int(time.time()) - 300:
            raise HTTPException(
                403,
                "Verify your password and second factor to continue",
                headers={"X-BSM-Recent-Auth": "required"},
            )
        return record

    async def verify_recent(self, user, identifier, password, otp, peer):
        from ..web.auth import authenticate_user

        await self.throttle(user.username, peer, "verify")
        if await authenticate_user(self.context, user.username, password) is None:
            raise HTTPException(401, "Verification failed")
        async with self.context.storage.transaction() as session:
            owner = await session.get(User, user.id)
            owner_id = owner.access_id
        if not await self.verify_factor(owner_id, otp):
            raise HTTPException(401, "Verification failed")
        record = await self.validate(identifier, owner_id, touch=False)
        if record is None:
            raise HTTPException(401, "Session no longer active")
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            await session.execute(
                update(LoginSession)
                .where(LoginSession.id == identifier, LoginSession.revoked_at.is_(None))
                .values(verified_at=now)
            )
            self.add_event(
                session, owner_id, "password_verified", {"session_id": identifier}
            )
        return now

    async def revoke(
        self, owner_id, *, identifier=None, except_id=None, reason="session_revoked"
    ):
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            query = select(LoginSession.id).where(
                LoginSession.owner_id == owner_id, LoginSession.revoked_at.is_(None)
            )
            if identifier is not None:
                query = query.where(LoginSession.id == identifier)
            if except_id is not None:
                query = query.where(LoginSession.id != except_id)
            ids = list((await session.scalars(query)).all())
            if identifier and not ids:
                existing = await session.get(LoginSession, identifier)
                if existing is None or existing.owner_id != owner_id:
                    raise HTTPException(404, "Session not found")
            await session.execute(
                update(LoginSession)
                .where(LoginSession.id.in_(ids))
                .values(revoked_at=now)
            )
            self.add_event(
                session, owner_id, reason, {"count": len(ids), "session_id": identifier}
            )
        manager = getattr(self.context, "_connection_manager", None)
        if manager:
            clients = [
                client
                for client in list(manager.active_connections.values())
                if getattr(client.authorization, "session_id", None) in ids
            ]
            await asyncio.gather(
                *(manager._authorization_changed(client) for client in clients),
                return_exceptions=True,
            )
        return len(ids)

    async def close_revoked(self, owner_id):
        manager = getattr(self.context, "_connection_manager", None)
        if manager is None:
            return
        clients = []
        for client in list(manager.active_connections.values()):
            authorization = client.authorization
            identifier = getattr(authorization, "session_id", None)
            if not identifier or authorization.owner_id != owner_id:
                continue
            try:
                valid = await self.validate(identifier, owner_id, touch=False)
            except Exception:
                valid = (
                    None  # Close interactive sockets if verification is unavailable.
                )
            if valid is None:
                clients.append(client)
        await asyncio.gather(
            *(manager._authorization_changed(client) for client in clients),
            return_exceptions=True,
        )

    async def revoke_in_transaction(self, session, owner_id, keep_id=None):
        query = update(LoginSession).where(
            LoginSession.owner_id == owner_id, LoginSession.revoked_at.is_(None)
        )
        if keep_id:
            query = query.where(LoginSession.id != keep_id)
        await session.execute(query.values(revoked_at=int(time.time())))

    async def revoke_owner(self, username, reason, except_id=None):
        async with self.context.storage.transaction() as session:
            owner = await session.scalar(select(User).where(User.username == username))
            owner_id = owner.access_id if owner else None
        if owner_id:
            await self.revoke(owner_id, except_id=except_id, reason=reason)

    async def list_sessions(self, owner_id, current_id=None):
        manager = getattr(self.context, "_connection_manager", None)
        connected = {
            getattr(client.authorization, "session_id", None)
            for client in (manager.active_connections.values() if manager else ())
        }
        async with self.context.storage.transaction() as session:
            rows = (
                await session.scalars(
                    select(LoginSession)
                    .where(
                        LoginSession.owner_id == owner_id,
                        LoginSession.expires_at > int(time.time()) - 90 * 86400,
                    )
                    .order_by(LoginSession.created_at.desc())
                    .limit(200)
                )
            ).all()
            now = int(time.time())
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "user_agent": row.user_agent,
                    "ip_address": row.ip_address,
                    "created_at": row.created_at,
                    "last_seen_at": row.last_seen_at,
                    "expires_at": row.expires_at,
                    "revoked_at": row.revoked_at,
                    "current": row.id == current_id,
                    "connected": row.id in connected and row.revoked_at is None,
                    "active": row.revoked_at is None
                    and row.expires_at > now
                    and row.last_seen_at + self.idle_seconds() > now,
                }
                for row in rows
            ]

    async def activity(self, owner_id):
        async with self.context.storage.transaction() as session:
            await session.execute(
                delete(AuthSecurityEvent).where(
                    AuthSecurityEvent.timestamp < int(time.time()) - 90 * 86400
                )
            )
            rows = (
                await session.scalars(
                    select(AuthSecurityEvent)
                    .where(AuthSecurityEvent.owner_id == owner_id)
                    .order_by(AuthSecurityEvent.timestamp.desc(), AuthSecurityEvent.id)
                    .limit(100)
                )
            ).all()
            return [
                {
                    "id": row.id,
                    "action": row.action,
                    "timestamp": row.timestamp,
                    "details": row.details,
                }
                for row in rows
            ]

    def _cipher(self, create=False):
        path = Path(self.context.config_dir) / "security" / "mfa.key"
        if create:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(Fernet.generate_key())
        try:
            return Fernet(path.read_bytes())
        except (OSError, ValueError) as error:
            raise HTTPException(
                503,
                "MFA key unavailable; restore the configuration key or use a recovery code",
            ) from error

    async def status(self, owner_id):
        async with self.context.storage.transaction() as session:
            row = await session.get(AccountSecurity, owner_id)
            return {
                "enabled": bool(row and row.totp_secret),
                "recovery_codes_remaining": len(row.recovery_hashes) if row else 0,
            }

    async def enrollment(self, owner_id, username):
        if (await self.status(owner_id))["enabled"]:
            raise HTTPException(409, "MFA is already enabled")
        key_path = Path(self.context.config_dir) / "security" / "mfa.key"
        if not key_path.exists():
            async with self.context.storage.transaction() as session:
                enrolled = await session.scalar(
                    select(AccountSecurity.owner_id)
                    .where(AccountSecurity.totp_secret.is_not(None))
                    .limit(1)
                )
            if enrolled:
                raise HTTPException(
                    503, "Restore the existing MFA configuration key before enrollment"
                )
        secret = pyotp.random_base32()
        encrypted = await run_in_thread(
            lambda: self._cipher(create=True).encrypt(secret.encode()).decode()
        )
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=username, issuer_name="Bedrock Server Manager"
        )

        def image():
            stream = io.BytesIO()
            qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage).save(stream)
            return base64.b64encode(stream.getvalue()).decode()

        svg = await run_in_thread(image)
        async with self.context.storage.transaction() as session:
            row = await session.get(AccountSecurity, owner_id)
            if row and row.totp_secret:
                raise HTTPException(409, "MFA is already enabled")
            if row is None:
                row = AccountSecurity(
                    owner_id=owner_id, recovery_hashes=[], last_counter=-1, version=0
                )
                session.add(row)
            row.version += 1
            row.pending_secret = encrypted
            row.pending_until = int(time.time()) + 600
        return {
            "secret": secret,
            "provisioning_uri": uri,
            "qr_svg": "data:image/svg+xml;base64," + svg,
        }

    async def _counter(self, encrypted, code):
        try:
            secret = await run_in_thread(
                lambda: self._cipher().decrypt(encrypted.encode()).decode()
            )
        except InvalidToken as error:
            raise HTTPException(503, "MFA configuration key does not match") from error
        if (
            not isinstance(code, str)
            or not code.isascii()
            or not code.isdigit()
            or len(code) != 6
        ):
            return None
        otp = pyotp.TOTP(secret)
        now = int(time.time()) // 30
        return next(
            (
                counter
                for counter in (now, now - 1, now + 1)
                if hmac.compare_digest(otp.at(counter * 30), code)
            ),
            None,
        )

    async def verify_factor(self, owner_id, code):
        async with self.context.storage.transaction() as session:
            row = await session.get(AccountSecurity, owner_id)
            if not row or not row.totp_secret:
                return True
            version = row.version
            recovery = hashlib.sha256(str(code).strip().lower().encode()).hexdigest()
            matched = next(
                (
                    value
                    for value in row.recovery_hashes
                    if hmac.compare_digest(value, recovery)
                ),
                None,
            )
            if matched:
                values = {
                    "recovery_hashes": [
                        value for value in row.recovery_hashes if value != matched
                    ]
                }
            else:
                counter = await self._counter(row.totp_secret, code)
                if counter is None or counter <= row.last_counter:
                    return False
                values = {"last_counter": counter}
            result = await session.execute(
                update(AccountSecurity)
                .where(
                    AccountSecurity.owner_id == owner_id,
                    AccountSecurity.version == version,
                )
                .values(**values, version=version + 1)
            )
            if result.rowcount != 1:
                return False
            if matched:
                self.add_event(session, owner_id, "recovery_code_used")
            return True

    @staticmethod
    def recovery_codes():
        codes = [secrets.token_hex(10) for _ in range(10)]
        return codes, [hashlib.sha256(code.encode()).hexdigest() for code in codes]

    async def confirm_enrollment(self, owner_id, code, keep_session_id=None):
        codes, hashes = self.recovery_codes()
        async with self.context.storage.transaction() as session:
            row = await session.get(AccountSecurity, owner_id)
            if (
                not row
                or not row.pending_secret
                or not row.pending_until
                or row.pending_until < int(time.time())
            ):
                raise HTTPException(400, "Enrollment expired; start again")
            counter = await self._counter(row.pending_secret, code)
            if counter is None:
                raise HTTPException(400, "Incorrect authenticator code")
            result = await session.execute(
                update(AccountSecurity)
                .where(
                    AccountSecurity.owner_id == owner_id,
                    AccountSecurity.version == row.version,
                    AccountSecurity.totp_secret.is_(None),
                )
                .values(
                    totp_secret=row.pending_secret,
                    pending_secret=None,
                    pending_until=None,
                    recovery_hashes=hashes,
                    last_counter=counter,
                    version=row.version + 1,
                )
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Enrollment changed; start again")
            self.add_event(session, owner_id, "mfa_enabled")
            await self.revoke_in_transaction(session, owner_id, keep_session_id)
        await self.close_revoked(owner_id)
        return {"recovery_codes": codes}

    async def change_factor(self, owner_id, *, disable=False, keep_session_id=None):
        codes, hashes = self.recovery_codes()
        async with self.context.storage.transaction() as session:
            row = await session.get(AccountSecurity, owner_id)
            if not row or not row.totp_secret:
                raise HTTPException(400, "MFA is not enabled")
            row.recovery_hashes = [] if disable else hashes
            row.version += 1
            if disable:
                row.totp_secret = None
                row.pending_secret = None
                row.pending_until = None
                await self.revoke_in_transaction(session, owner_id, keep_session_id)
            self.add_event(
                session,
                owner_id,
                "mfa_disabled" if disable else "recovery_codes_rotated",
            )
        if disable:
            await self.close_revoked(owner_id)
        return {"recovery_codes": [] if disable else codes}

    async def revoke_credentials(self, owner_id):
        async with self.context.storage.transaction() as session:
            await session.execute(
                update(IntegrationToken)
                .where(
                    IntegrationToken.owner_id == owner_id,
                    IntegrationToken.revoked_at.is_(None),
                )
                .values(revoked_at=int(time.time()))
            )
            self.add_event(session, owner_id, "all_integration_credentials_revoked")
        await self.context.access_service.notify(kind="credentials_changed")
