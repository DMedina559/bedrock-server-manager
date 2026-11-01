"""Persisted login families, bounded authentication and factor verification."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import io
import ipaddress
import logging
import secrets
import time
from pathlib import Path
from uuid import uuid4

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import and_, case, delete, func, or_, select, tuple_, update
from sqlalchemy.exc import IntegrityError

from ..db.models import (
    AccountSecurity,
    AccountServerAccess,
    AuthSecurityEvent,
    AuthThrottle,
    IntegrationToken,
    LoginSession,
    PasskeyChallenge,
    PasskeyCredential,
    ServerAccessGrant,
    TrustedDevice,
    User,
)
from ..utils.threads import run_in_thread
from .webauthn import (
    COSE_ALG_EDDSA,
    COSE_ALG_ES256,
    COSE_ALG_RS256,
    PasskeyCounterRegressionError,
    WebAuthnError,
    b64url_decode,
    b64url_encode,
    resolve_rp_and_origins,
    verify_authentication_response,
    verify_registration_response,
)


class SessionService:
    def __init__(self, context):
        self.context = context
        self._maintenance_task = None

    def idle_seconds(self):
        return max(
            300,
            min(
                int(self.context.settings.get("security.session_idle_hours", 24))
                * 3600,
                28 * 86400,
            ),
        )

    async def publish(self, owner_id, action):
        """Deliver only fixed, non-secret security facts after their transaction commits."""
        if action not in {
            "login",
            "passkey_login",
            "passkey_registered",
            "passkey_revoked",
            "passkey_verified",
            "passkey_clone_detected",
            "trusted_device_remembered",
            "trusted_devices_revoked",
            "role_changed",
            "account_disabled",
            "account_enabled",
            "recovery_code_used",
            "mfa_enabled",
            "mfa_disabled",
            "recovery_codes_rotated",
            "password_changed",
            "password_reset",
            "local_mfa_reset",
            "integration_credential_created",
            "integration_credential_rotated",
            "integration_credential_revoked",
            "all_integration_credentials_revoked",
            "registration_token_created",
            "account_registered",
        }:
            return
        payload = {
            "event_id": uuid4().hex,
            "owner_id": owner_id,
            "action": action,
            "timestamp": int(time.time()),
        }
        try:
            async with self.context.storage.transaction() as session:
                username = await session.scalar(
                    select(User.username).where(User.access_id == owner_id)
                )
            manager = getattr(self.context, "_connection_manager", None)
            if manager is not None and username:
                await manager.send_to_user(
                    username, {"type": "security_event", **payload}
                )
            await self.context.events.emit("on_account_security", payload, public=False)
        except Exception:
            logging.getLogger(__name__).warning(
                "Security notification delivery unavailable"
            )

    async def event(self, user_id, action, **details):
        async with self.context.storage.transaction() as session:
            user = await session.get(User, user_id)
            if user is not None:
                self.add_event(session, user.access_id, action, details)
        if user is not None:
            await self.publish(user.access_id, action)

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

    def peer_key(self, peer):
        """Canonicalize the already trusted ASGI client, never raw forwarding headers."""
        try:
            address = ipaddress.ip_address(peer)
        except ValueError:
            return peer
        if isinstance(address, ipaddress.IPv6Address):
            if address.ipv4_mapped is not None:
                return str(address.ipv4_mapped)
            prefix = self.context.settings.get("security.auth_ipv6_prefix", 128)
            return str(ipaddress.ip_network((address, prefix), strict=False))
        return str(address)

    async def throttle(self, username="", peer="", operation="login"):
        # Consume IP first: arbitrary usernames cannot create unbounded rows per peer.
        window_seconds = int(
            self.context.settings.get("security.auth_window_seconds", 300)
        )
        checks = [
            (
                f"peer:{self.peer_key(peer)}",
                int(self.context.settings.get("security.auth_peer_attempts", 60)),
            )
        ]
        if username:
            checks.append(
                (
                    f"{operation}:{username.casefold()}",
                    int(
                        self.context.settings.get("security.auth_account_attempts", 10)
                    ),
                )
            )
        for value, limit in checks:
            key = hashlib.sha256(value.encode()).hexdigest()
            now = int(time.time())
            window = now - now % window_seconds
            for retry in range(2):
                try:
                    async with self.context.storage.transaction() as session:
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
                    headers={"Retry-After": str(window_seconds - now % window_seconds)},
                )

    async def authentication_succeeded(self, username, operation="login"):
        key = hashlib.sha256(f"{operation}:{username.casefold()}".encode()).hexdigest()
        async with self.context.storage.transaction() as session:
            await session.execute(delete(AuthThrottle).where(AuthThrottle.key == key))

    async def start(self):
        """Own retention independently of traffic and of the HTTP lifespan."""
        if self._maintenance_task is None or self._maintenance_task.done():
            self._maintenance_task = asyncio.create_task(
                self._maintain(), name="authentication-retention"
            )

    async def shutdown(self):
        task = self._maintenance_task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self._maintenance_task = None

    async def _maintain(self):
        while True:
            delay = 86400
            try:
                await self.cleanup()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Authentication retention failed; retrying in five minutes"
                )
                delay = 300
            await asyncio.sleep(delay)

    async def cleanup(self):
        """Delete expired metadata in bounded transactions, yielding between batches."""
        now = int(time.time())
        # Delete by primary key, rather than by owner, to bound even large histories.
        for model in (
            AccountSecurity,
            AccountServerAccess,
            IntegrationToken,
            PasskeyChallenge,
            PasskeyCredential,
            TrustedDevice,
            ServerAccessGrant,
        ):
            columns = list(model.__table__.primary_key.columns)
            key = columns[0] if len(columns) == 1 else tuple_(*columns)
            orphan = (
                ~select(User.access_id).where(User.access_id == model.owner_id).exists()
            )
            while True:
                async with self.context.storage.transaction() as session:
                    rows = list(
                        (
                            await session.execute(
                                select(*columns)
                                .where(orphan)
                                .order_by(*columns)
                                .limit(250)
                            )
                        ).all()
                    )
                    ids = [row[0] for row in rows] if len(columns) == 1 else rows
                    if ids:
                        await session.execute(delete(model).where(key.in_(ids), orphan))
                if len(rows) < 250:
                    break
                await asyncio.sleep(0)
        for model, key, predicate in (
            (
                IntegrationToken,
                IntegrationToken.id,
                or_(
                    IntegrationToken.revoked_at < now - 90 * 86400,
                    and_(
                        IntegrationToken.expires_at.is_not(None),
                        IntegrationToken.expires_at < now - 90 * 86400,
                    ),
                ),
            ),
            (
                TrustedDevice,
                TrustedDevice.id,
                TrustedDevice.expires_at < now - 90 * 86400,
            ),
            (
                PasskeyCredential,
                PasskeyCredential.id,
                and_(
                    PasskeyCredential.revoked_at.is_not(None),
                    PasskeyCredential.revoked_at < now - 90 * 86400,
                ),
            ),
            (
                PasskeyChallenge,
                PasskeyChallenge.id,
                PasskeyChallenge.expires_at < now - 300,
            ),
            (AuthThrottle, AuthThrottle.key, AuthThrottle.window < now - 86400),
            (
                AuthSecurityEvent,
                AuthSecurityEvent.id,
                AuthSecurityEvent.timestamp < now - 90 * 86400,
            ),
            (LoginSession, LoginSession.id, LoginSession.expires_at < now - 90 * 86400),
        ):
            while True:
                async with self.context.storage.transaction() as session:
                    ids = list(
                        (
                            await session.scalars(
                                select(key).where(predicate).order_by(key).limit(250)
                            )
                        ).all()
                    )
                    if ids:
                        await session.execute(
                            delete(model).where(key.in_(ids), predicate)
                        )
                if len(ids) < 250:
                    break
                await asyncio.sleep(0)

    @staticmethod
    async def advance_auth_revision(session, owner_id, keep_session_id=None):
        await session.execute(
            update(User)
            .where(User.access_id == owner_id)
            .values(auth_revision=User.auth_revision + 1)
        )
        query = update(LoginSession).where(LoginSession.owner_id == owner_id)
        if keep_session_id:
            query = query.where(LoginSession.id != keep_session_id)
        await session.execute(query.values(verified_at=0))

    async def create(
        self, owner_id, expires_at, expected_revision=None, factor_proof=None
    ):
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
            verified_device_id = (
                await self.context.trusted_device_service.session_proof(
                    session, current, factor_proof
                )
                if factor_proof
                else None
            )
            count = await session.scalar(
                select(func.count())
                .select_from(LoginSession)
                .where(
                    LoginSession.owner_id == owner_id,
                    LoginSession.revoked_at.is_(None),
                    LoginSession.expires_at > now,
                    LoginSession.last_seen_at > now - self.idle_seconds(),
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
                verified_device_id=verified_device_id,
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

    @staticmethod
    def client_metadata(request):
        agent = request.headers.get("user-agent", "")[:512]
        name = request.headers.get("x-bsm-client", "")[:100].strip()
        if not name:
            browser = next(
                (
                    label
                    for marker, label in (
                        ("Electron/", "Electron"),
                        ("Tauri/", "Tauri"),
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
        return {
            "name": name,
            "user_agent": agent,
            "ip_address": (request.client.host if request.client else "")[:64],
        }

    async def annotate(self, identifier, request):
        async with self.context.storage.transaction() as session:
            await session.execute(
                update(LoginSession)
                .where(LoginSession.id == identifier)
                .values(**self.client_metadata(request))
            )

    async def require_recent(self, user, identifier):
        record = await self.validate(identifier, touch=False)
        if record is None:
            raise HTTPException(401, "Sign in again to manage security settings")
        async with self.context.storage.transaction() as session:
            owner = await session.get(User, user.id)
            if owner is None or owner.access_id != record.owner_id:
                raise HTTPException(403, "Session owner mismatch")
            device_valid = (
                record.verified_device_id is None
                or await self.context.trusted_device_service.live_record(
                    session, record.owner_id, record.verified_device_id
                )
                is not None
            )
        if not device_valid or record.verified_at < int(time.time()) - 300:
            raise HTTPException(
                403,
                "Verify your password and second factor to continue",
                headers={"X-BSM-Recent-Auth": "required"},
            )
        return record

    async def verify_recent(
        self, user, identifier, password, otp, peer, trusted_device_token=None
    ):
        from ..web.auth import authenticate_user

        await self.throttle(user.username, peer, "verify")
        async with self.context.storage.transaction() as session:
            owner = await session.get(User, user.id)
            if owner is None or not owner.is_active:
                raise HTTPException(401, "Verification failed")
            owner_id, revision = owner.access_id, owner.auth_revision
        if await authenticate_user(self.context, user.username, password) is None:
            raise HTTPException(401, "Verification failed")
        proof = await self.context.trusted_device_service.verify_factor(
            owner_id, revision, otp, trusted_device_token
        )
        if proof is None:
            raise HTTPException(
                401,
                "Authenticator or recovery code required",
                headers={"X-BSM-MFA": "required"},
            )
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            current = await session.scalar(
                select(User).where(User.access_id == owner_id).with_for_update()
            )
            if (
                current is None
                or not current.is_active
                or current.auth_revision != revision
            ):
                raise HTTPException(401, "Account security changed; verify again")
            verified_device_id = (
                await self.context.trusted_device_service.session_proof(
                    session, current, proof
                )
            )
            result = await session.execute(
                update(LoginSession)
                .where(
                    LoginSession.id == identifier,
                    LoginSession.owner_id == owner_id,
                    LoginSession.revoked_at.is_(None),
                    LoginSession.expires_at > now,
                    LoginSession.last_seen_at > now - self.idle_seconds(),
                )
                .values(verified_at=now, verified_device_id=verified_device_id)
            )
            if result.rowcount != 1:
                raise HTTPException(401, "Session no longer active")
            self.add_event(
                session, owner_id, "password_verified", {"session_id": identifier}
            )
        await self.authentication_succeeded(user.username, "verify")
        return now, proof

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
                    .order_by(
                        case(
                            (
                                (LoginSession.revoked_at.is_(None))
                                & (LoginSession.expires_at > int(time.time()))
                                & (
                                    LoginSession.last_seen_at
                                    > int(time.time()) - self.idle_seconds()
                                ),
                                0,
                            ),
                            else_=1,
                        ),
                        LoginSession.created_at.desc(),
                        LoginSession.id.desc(),
                    )
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
                    "expired_reason": (
                        "absolute"
                        if row.expires_at <= now
                        else (
                            "idle"
                            if row.last_seen_at + self.idle_seconds() <= now
                            else None
                        )
                    ),
                    "active": row.revoked_at is None
                    and row.expires_at > now
                    and row.last_seen_at + self.idle_seconds() > now,
                }
                for row in rows
            ]

    async def activity(self, owner_id):
        async with self.context.storage.transaction() as session:
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

    def _mfa_key_path(self) -> Path:
        return Path(self.context.config_dir) / "credentials" / "mfa.key"

    def _cipher(self, create=False):
        from ..backups import credentials

        path = self._mfa_key_path()
        lock_path = path.parent / ".mfa.key.lock"
        try:
            if create:
                credentials.private_directory(path.parent)
                with credentials.locked_credential_file(
                    lock_path,
                    busy_message="MFA key is busy; retry shortly.",
                ):
                    if not path.exists():
                        credentials.atomic_bytes(path, Fernet.generate_key() + b"\n")
            credentials.protect(path.parent, directory=True)
            credentials.protect(path)
            return Fernet(path.read_bytes().strip())
        except (OSError, ValueError) as error:
            raise HTTPException(
                503,
                "MFA key unavailable; restore the configuration key or use a recovery code",
            ) from error

    async def has_active_passkeys(self, owner_id: str) -> bool:
        async with self.context.storage.transaction() as session:
            return (
                await session.scalar(
                    select(PasskeyCredential.id)
                    .where(
                        PasskeyCredential.owner_id == owner_id,
                        PasskeyCredential.revoked_at.is_(None),
                    )
                    .limit(1)
                )
                is not None
            )

    async def status(self, owner_id):
        async with self.context.storage.transaction() as session:
            row = await session.get(AccountSecurity, owner_id)
            passkey_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(PasskeyCredential)
                    .where(
                        PasskeyCredential.owner_id == owner_id,
                        PasskeyCredential.revoked_at.is_(None),
                    )
                )
                or 0
            )
            return {
                "enabled": bool(row and row.totp_secret),
                "recovery_codes_remaining": len(row.recovery_hashes) if row else 0,
                "passkeys_enabled": passkey_count > 0,
                "passkey_count": passkey_count,
            }

    async def enrollment(self, owner_id, username):
        if (await self.status(owner_id))["enabled"]:
            raise HTTPException(409, "MFA is already enabled")
        key_path = self._mfa_key_path()
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
            revision = await session.scalar(
                select(User.auth_revision).where(
                    User.access_id == owner_id, User.is_active.is_(True)
                )
            )
            if revision is None:
                return False
            if not row or not row.totp_secret:
                return True
            version, encrypted, last_counter = (
                row.version,
                row.totp_secret,
                row.last_counter,
            )
            hashes = tuple(row.recovery_hashes)
        recovery = hashlib.sha256(str(code).strip().lower().encode()).hexdigest()
        matched = next(
            (value for value in hashes if hmac.compare_digest(value, recovery)), None
        )
        if matched:
            values = {
                "recovery_hashes": [value for value in hashes if value != matched]
            }
        else:
            counter = await self._counter(encrypted, code)
            if counter is None or counter <= last_counter:
                return False
            values = {"last_counter": counter}
        async with self.context.storage.transaction() as session:
            result = await session.execute(
                update(AccountSecurity)
                .where(
                    AccountSecurity.owner_id == owner_id,
                    AccountSecurity.version == version,
                    AccountSecurity.totp_secret == encrypted,
                    select(User.access_id)
                    .where(
                        User.access_id == owner_id,
                        User.auth_revision == revision,
                        User.is_active.is_(True),
                    )
                    .exists(),
                )
                .values(**values, version=version + 1)
            )
            if result.rowcount != 1:
                return False
            if matched:
                self.add_event(session, owner_id, "recovery_code_used")
        if matched:
            await self.publish(owner_id, "recovery_code_used")
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
            version, pending, deadline = (
                row.version,
                row.pending_secret,
                row.pending_until,
            )
            revision = await session.scalar(
                select(User.auth_revision).where(
                    User.access_id == owner_id, User.is_active.is_(True)
                )
            )
        counter = await self._counter(pending, code)
        if counter is None:
            raise HTTPException(400, "Incorrect authenticator code")
        async with self.context.storage.transaction() as session:
            result = await session.execute(
                update(AccountSecurity)
                .where(
                    AccountSecurity.owner_id == owner_id,
                    AccountSecurity.version == version,
                    AccountSecurity.pending_secret == pending,
                    AccountSecurity.pending_until == deadline,
                    AccountSecurity.pending_until >= int(time.time()),
                    select(User.access_id)
                    .where(
                        User.access_id == owner_id,
                        User.auth_revision == revision,
                        User.is_active.is_(True),
                    )
                    .exists(),
                    AccountSecurity.totp_secret.is_(None),
                )
                .values(
                    totp_secret=pending,
                    pending_secret=None,
                    pending_until=None,
                    recovery_hashes=hashes,
                    last_counter=counter,
                    version=version + 1,
                )
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Enrollment changed; start again")
            await self.advance_auth_revision(session, owner_id, keep_session_id)
            self.add_event(session, owner_id, "mfa_enabled")
            await self.revoke_in_transaction(session, owner_id, keep_session_id)
        await self.close_revoked(owner_id)
        await self.publish(owner_id, "mfa_enabled")
        return {"recovery_codes": codes}

    async def change_factor(
        self,
        owner_id,
        *,
        disable=False,
        reset_passkeys=False,
        keep_session_id=None,
        keep_trusted_device=None,
    ):
        codes, hashes = self.recovery_codes()
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            row = await session.get(AccountSecurity, owner_id)
            has_totp = bool(row and row.totp_secret)
            has_passkey = False
            if reset_passkeys:
                has_passkey = (
                    await session.scalar(
                        select(PasskeyCredential.id)
                        .where(
                            PasskeyCredential.owner_id == owner_id,
                            PasskeyCredential.revoked_at.is_(None),
                        )
                        .limit(1)
                    )
                    is not None
                )
            if not has_totp and not (reset_passkeys and has_passkey):
                raise HTTPException(400, "MFA is not enabled")
            await self.advance_auth_revision(session, owner_id, keep_session_id)
            if (
                not disable
                and keep_trusted_device is not None
                and keep_trusted_device.owner_id == owner_id
            ):
                # Keep this device's existing absolute deadline; never renew trust
                # merely because an older remembered credential was presented.
                revision = await session.scalar(
                    select(User.auth_revision).where(User.access_id == owner_id)
                )
                await session.execute(
                    update(TrustedDevice)
                    .where(
                        TrustedDevice.id == keep_trusted_device.id,
                        TrustedDevice.owner_id == owner_id,
                        TrustedDevice.auth_revision == revision - 1,
                        TrustedDevice.revoked_at.is_(None),
                        TrustedDevice.expires_at > now,
                    )
                    .values(auth_revision=revision)
                )

            if row is not None:
                row.recovery_hashes = [] if disable else hashes
                row.version += 1
                if disable:
                    row.totp_secret = None
                    row.pending_secret = None
                    row.pending_until = None
            if disable and reset_passkeys:
                await session.execute(
                    update(PasskeyCredential)
                    .where(
                        PasskeyCredential.owner_id == owner_id,
                        PasskeyCredential.revoked_at.is_(None),
                    )
                    .values(revoked_at=now)
                )
            if disable:
                await self.revoke_in_transaction(session, owner_id, keep_session_id)
            self.add_event(
                session,
                owner_id,
                "mfa_disabled" if disable else "recovery_codes_rotated",
            )
        if disable:
            await self.close_revoked(owner_id)
        await self.publish(
            owner_id, "mfa_disabled" if disable else "recovery_codes_rotated"
        )
        return {"recovery_codes": [] if disable else codes}

    @staticmethod
    def _passkey_info(row: PasskeyCredential) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "transports": list(row.transports or []),
            "aaguid": row.aaguid,
            "user_verified": bool(row.user_verified),
            "backup_eligible": bool(row.backup_eligible),
            "backup_state": bool(row.backup_state),
            "created_at": row.created_at,
            "last_used_at": row.last_used_at,
            "revoked_at": row.revoked_at,
            "active": row.revoked_at is None,
        }

    async def list_passkeys(self, owner_id: str) -> list[dict]:
        async with self.context.storage.transaction() as session:
            rows = (
                await session.scalars(
                    select(PasskeyCredential)
                    .where(PasskeyCredential.owner_id == owner_id)
                    .order_by(
                        case((PasskeyCredential.revoked_at.is_(None), 0), else_=1),
                        PasskeyCredential.created_at.desc(),
                        PasskeyCredential.id.desc(),
                    )
                    .limit(100)
                )
            ).all()
            return [self._passkey_info(row) for row in rows]

    async def begin_passkey_registration(self, owner_id: str, username: str, request):
        rp_id, _ = resolve_rp_and_origins(request, self.context.settings)
        now = int(time.time())
        challenge_id = uuid4().hex
        challenge = b64url_encode(secrets.token_bytes(32))
        async with self.context.storage.transaction() as session:
            user = await session.scalar(
                select(User).where(User.access_id == owner_id, User.is_active.is_(True))
            )
            if user is None:
                raise HTTPException(401, "Account not found")
            existing = list(
                await session.scalars(
                    select(PasskeyCredential).where(
                        PasskeyCredential.owner_id == owner_id,
                        PasskeyCredential.revoked_at.is_(None),
                    )
                )
            )
            if len(existing) >= 20:
                raise HTTPException(
                    409, "Remove an unused passkey before registering another"
                )
            session.add(
                PasskeyChallenge(
                    id=challenge_id,
                    owner_id=owner_id,
                    purpose="register",
                    challenge=challenge,
                    rp_id=rp_id,
                    created_at=now,
                    expires_at=now + 300,
                )
            )
            display_name = (user.full_name or user.username).strip() or user.username
        exclude_credentials = [
            {
                "type": "public-key",
                "id": item.credential_id,
                **({"transports": item.transports} if item.transports else {}),
            }
            for item in existing
        ]
        return {
            "challenge_id": challenge_id,
            "public_key": {
                "challenge": challenge,
                "rp": {"name": "Bedrock Server Manager", "id": rp_id},
                "user": {
                    "id": b64url_encode(owner_id.encode("utf-8")),
                    "name": username,
                    "displayName": display_name,
                },
                "pubKeyCredParams": [
                    {"type": "public-key", "alg": COSE_ALG_ES256},
                    {"type": "public-key", "alg": COSE_ALG_EDDSA},
                    {"type": "public-key", "alg": COSE_ALG_RS256},
                ],
                "timeout": 60000,
                "attestation": "none",
                "authenticatorSelection": {
                    "residentKey": "preferred",
                    "userVerification": "preferred",
                },
                "excludeCredentials": exclude_credentials,
            },
        }

    async def complete_passkey_registration(
        self, owner_id: str, payload, request
    ) -> dict:
        _, allowed_origins = resolve_rp_and_origins(request, self.context.settings)
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            challenge_row = await session.get(PasskeyChallenge, payload.challenge_id)
            if (
                challenge_row is None
                or challenge_row.purpose != "register"
                or challenge_row.owner_id != owner_id
                or challenge_row.expires_at < now
            ):
                if challenge_row is not None:
                    await session.delete(challenge_row)
                raise HTTPException(
                    400, "Passkey registration challenge expired or invalid"
                )
            expected_challenge = challenge_row.challenge
            expected_rp_id = challenge_row.rp_id
            await session.delete(challenge_row)

        try:
            verified = verify_registration_response(
                credential=payload.credential,
                expected_challenge=expected_challenge,
                expected_rp_id=expected_rp_id,
                allowed_origins=allowed_origins,
            )
        except WebAuthnError as error:
            raise HTTPException(400, str(error)) from error

        raw_transports = (
            payload.credential.get("response", {}).get("transports")
            if isinstance(payload.credential.get("response"), dict)
            else None
        )
        allowed_transports = {
            "ble",
            "cable",
            "hybrid",
            "internal",
            "nfc",
            "smart-card",
            "usb",
        }
        transports = (
            sorted(
                {
                    str(item)
                    for item in raw_transports
                    if isinstance(item, str) and item in allowed_transports
                }
            )
            if isinstance(raw_transports, list)
            else []
        )
        default_name = self.client_metadata(request)["name"] or "Passkey"
        passkey_name = (payload.name or default_name).strip()[:100] or "Passkey"
        passkey_id = uuid4().hex

        async with self.context.storage.transaction() as session:
            user = await session.scalar(
                select(User).where(User.access_id == owner_id, User.is_active.is_(True))
            )
            if user is None:
                raise HTTPException(401, "Account not found")
            existing_cred = await session.scalar(
                select(PasskeyCredential).where(
                    PasskeyCredential.credential_id == verified.credential_id
                )
            )
            if existing_cred is not None:
                raise HTTPException(409, "Passkey is already registered")
            count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(PasskeyCredential)
                    .where(
                        PasskeyCredential.owner_id == owner_id,
                        PasskeyCredential.revoked_at.is_(None),
                    )
                )
                or 0
            )
            if count >= 20:
                raise HTTPException(
                    409, "Remove an unused passkey before registering another"
                )
            row = PasskeyCredential(
                id=passkey_id,
                owner_id=owner_id,
                credential_id=verified.credential_id,
                public_key=verified.public_key,
                sign_count=verified.sign_count,
                name=passkey_name,
                transports=transports,
                aaguid=verified.aaguid,
                user_verified=verified.user_verified,
                backup_eligible=verified.backup_eligible,
                backup_state=verified.backup_state,
                created_at=now,
            )
            session.add(row)
            self.add_event(
                session,
                owner_id,
                "passkey_registered",
                {"passkey_id": passkey_id, "name": passkey_name},
            )
            info = self._passkey_info(row)
        await self.publish(owner_id, "passkey_registered")
        return info

    async def rename_passkey(self, owner_id: str, passkey_id: str, name: str) -> dict:
        async with self.context.storage.transaction() as session:
            row = await session.get(PasskeyCredential, passkey_id)
            if row is None or row.owner_id != owner_id or row.revoked_at is not None:
                raise HTTPException(404, "Passkey not found")
            row.name = name.strip()[:100]
            return self._passkey_info(row)

    async def revoke_passkey(
        self, owner_id: str, passkey_id: str, *, is_admin_role: bool = False
    ) -> None:
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            row = await session.get(PasskeyCredential, passkey_id)
            if row is None or row.owner_id != owner_id or row.revoked_at is not None:
                raise HTTPException(404, "Passkey not found")
            if is_admin_role and self.context.settings.get(
                "security.require_admin_mfa", False
            ):
                factor = await session.get(AccountSecurity, owner_id)
                has_totp = bool(factor and factor.totp_secret)
                other_passkeys = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(PasskeyCredential)
                        .where(
                            PasskeyCredential.owner_id == owner_id,
                            PasskeyCredential.id != passkey_id,
                            PasskeyCredential.revoked_at.is_(None),
                        )
                    )
                    or 0
                )
                if not has_totp and other_passkeys == 0:
                    raise HTTPException(
                        403,
                        "Administrator MFA is required; enroll a replacement factor or use local recovery",
                    )
            row.revoked_at = now
            self.add_event(
                session,
                owner_id,
                "passkey_revoked",
                {"passkey_id": passkey_id, "name": row.name},
            )
        await self.publish(owner_id, "passkey_revoked")

    async def begin_passkey_authentication(
        self,
        request,
        *,
        username: str | None = None,
        purpose: str = "login",
        owner_id: str | None = None,
    ) -> dict:
        rp_id, _ = resolve_rp_and_origins(request, self.context.settings)
        now = int(time.time())
        challenge_id = uuid4().hex
        challenge = b64url_encode(secrets.token_bytes(32))
        allow_credentials: list[dict] = []

        async with self.context.storage.transaction() as session:
            resolved_owner = owner_id
            if purpose == "login" and username:
                user = await self.context.storage.user_repo.get_user_by_username(
                    session, username.strip()
                )
                if user is not None and user.is_active:
                    resolved_owner = user.access_id
            if resolved_owner:
                rows = list(
                    await session.scalars(
                        select(PasskeyCredential).where(
                            PasskeyCredential.owner_id == resolved_owner,
                            PasskeyCredential.revoked_at.is_(None),
                        )
                    )
                )
                if purpose == "verify" and not rows:
                    raise HTTPException(400, "No active passkeys are registered")
                allow_credentials = [
                    {
                        "type": "public-key",
                        "id": row.credential_id,
                        **({"transports": row.transports} if row.transports else {}),
                    }
                    for row in rows
                ]
            session.add(
                PasskeyChallenge(
                    id=challenge_id,
                    owner_id=resolved_owner,
                    purpose=purpose,
                    challenge=challenge,
                    rp_id=rp_id,
                    created_at=now,
                    expires_at=now + 300,
                )
            )
        return {
            "challenge_id": challenge_id,
            "public_key": {
                "challenge": challenge,
                "rpId": rp_id,
                "timeout": 60000,
                "userVerification": "preferred",
                "allowCredentials": allow_credentials,
            },
        }

    async def _consume_and_verify_assertion(
        self,
        *,
        challenge_id: str,
        credential: dict,
        purpose: str,
        expected_owner_id: str | None,
        request,
    ) -> tuple[User, PasskeyCredential]:
        _, allowed_origins = resolve_rp_and_origins(request, self.context.settings)
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            challenge_row = await session.get(PasskeyChallenge, challenge_id)
            if (
                challenge_row is None
                or challenge_row.purpose != purpose
                or challenge_row.expires_at < now
                or (
                    expected_owner_id is not None
                    and challenge_row.owner_id != expected_owner_id
                )
            ):
                if challenge_row is not None:
                    await session.delete(challenge_row)
                raise HTTPException(401, "Passkey challenge expired or invalid")
            expected_challenge = challenge_row.challenge
            expected_rp_id = challenge_row.rp_id
            challenge_owner_id = challenge_row.owner_id
            await session.delete(challenge_row)

        raw_id = credential.get("rawId") or credential.get("id")
        try:
            normalized_id = b64url_encode(b64url_decode(str(raw_id or "")))
        except WebAuthnError as error:
            raise HTTPException(401, "Invalid passkey credential identifier") from error

        async with self.context.storage.transaction() as session:
            passkey = await session.scalar(
                select(PasskeyCredential).where(
                    PasskeyCredential.credential_id == normalized_id,
                    PasskeyCredential.revoked_at.is_(None),
                )
            )
            if passkey is None:
                raise HTTPException(401, "Passkey authentication failed")
            if (
                challenge_owner_id is not None
                and passkey.owner_id != challenge_owner_id
            ):
                raise HTTPException(401, "Passkey authentication failed")
            if expected_owner_id is not None and passkey.owner_id != expected_owner_id:
                raise HTTPException(401, "Passkey authentication failed")
            owner = await session.scalar(
                select(User).where(
                    User.access_id == passkey.owner_id, User.is_active.is_(True)
                )
            )
            if owner is None:
                raise HTTPException(401, "Passkey authentication failed")
            public_key_b64 = passkey.public_key
            stored_sign_count = passkey.sign_count
            passkey_pk = passkey.id
            owner_access_id = owner.access_id

        try:
            verified = verify_authentication_response(
                credential=credential,
                expected_challenge=expected_challenge,
                expected_rp_id=expected_rp_id,
                allowed_origins=allowed_origins,
                public_key_b64=public_key_b64,
                stored_sign_count=stored_sign_count,
            )
        except PasskeyCounterRegressionError as error:
            async with self.context.storage.transaction() as session:
                self.add_event(
                    session,
                    owner_access_id,
                    "passkey_clone_detected",
                    {"passkey_id": passkey_pk},
                )
            await self.publish(owner_access_id, "passkey_clone_detected")
            raise HTTPException(
                401, "Passkey signature counter regression detected"
            ) from error
        except WebAuthnError as error:
            raise HTTPException(401, "Passkey authentication failed") from error

        async with self.context.storage.transaction() as session:
            current_owner = await session.scalar(
                select(User)
                .where(User.access_id == owner_access_id, User.is_active.is_(True))
                .with_for_update()
            )
            current_passkey = await session.get(PasskeyCredential, passkey_pk)
            if (
                current_owner is None
                or current_passkey is None
                or current_passkey.revoked_at is not None
            ):
                raise HTTPException(401, "Passkey authentication failed")
            if (
                stored_sign_count > 0 or verified.sign_count > 0
            ) and verified.sign_count <= current_passkey.sign_count:
                self.add_event(
                    session,
                    owner_access_id,
                    "passkey_clone_detected",
                    {"passkey_id": passkey_pk},
                )
                raise HTTPException(
                    401, "Passkey signature counter regression detected"
                )
            current_passkey.sign_count = verified.sign_count
            current_passkey.last_used_at = now
            current_passkey.backup_eligible = verified.backup_eligible
            current_passkey.backup_state = verified.backup_state
            return current_owner, current_passkey

    async def complete_passkey_login(self, payload, request) -> tuple[str, str, int]:
        peer = request.client.host if request.client else ""
        await self.throttle("", peer, "passkey_login")
        owner, passkey = await self._consume_and_verify_assertion(
            challenge_id=payload.challenge_id,
            credential=payload.credential,
            purpose="login",
            expected_owner_id=None,
            request=request,
        )
        async with self.context.storage.transaction() as session:
            self.add_event(
                session,
                owner.access_id,
                "passkey_login",
                {"passkey_id": passkey.id, "name": passkey.name},
            )
        await self.authentication_succeeded(owner.username, "passkey_login")
        await self.publish(owner.access_id, "passkey_login")
        return owner.username, owner.access_id, owner.auth_revision

    async def verify_recent_passkey(
        self, user, identifier: str, payload, request
    ) -> int:
        peer = request.client.host if request.client else ""
        await self.throttle(user.username, peer, "verify")
        async with self.context.storage.transaction() as session:
            owner = await session.get(User, user.id)
            if owner is None or not owner.is_active:
                raise HTTPException(401, "Verification failed")
            owner_id, revision = owner.access_id, owner.auth_revision

        _, passkey = await self._consume_and_verify_assertion(
            challenge_id=payload.challenge_id,
            credential=payload.credential,
            purpose="verify",
            expected_owner_id=owner_id,
            request=request,
        )
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            current = await session.scalar(
                select(User).where(User.access_id == owner_id).with_for_update()
            )
            if (
                current is None
                or not current.is_active
                or current.auth_revision != revision
            ):
                raise HTTPException(401, "Account security changed; verify again")
            result = await session.execute(
                update(LoginSession)
                .where(
                    LoginSession.id == identifier,
                    LoginSession.owner_id == owner_id,
                    LoginSession.revoked_at.is_(None),
                    LoginSession.expires_at > now,
                    LoginSession.last_seen_at > now - self.idle_seconds(),
                )
                .values(verified_at=now, verified_device_id=None)
            )
            if result.rowcount != 1:
                raise HTTPException(401, "Session no longer active")
            self.add_event(
                session,
                owner_id,
                "passkey_verified",
                {"session_id": identifier, "passkey_id": passkey.id},
            )
        await self.authentication_succeeded(user.username, "verify")
        await self.publish(owner_id, "passkey_verified")
        return now

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
        await self.publish(owner_id, "all_integration_credentials_revoked")
        await self.context.access_service.notify(kind="credentials_changed")
