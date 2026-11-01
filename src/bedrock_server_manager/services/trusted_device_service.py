"""Server-validated remembered second factors, never cached authorization grants."""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import case, select, update

from ..db.models import (
    AccountSecurity,
    LoginSession,
    PasskeyCredential,
    TrustedDevice,
    User,
)

TRUST_DAYS = 30
MAX_DEVICES = 20


@dataclass(frozen=True)
class FactorProof:
    owner_id: str
    auth_revision: int
    fresh_factor: bool
    device_id: str | None = None
    passkey_id: str | None = None


class TrustedDeviceService:
    def __init__(self, context):
        self.context = context

    @staticmethod
    def identifier(token):
        if not isinstance(token, str) or not 40 < len(token) <= 256:
            return None
        prefix, separator, secret = token.partition(".")
        identifier = prefix.removeprefix("bsm_td_")
        if (
            not prefix.startswith("bsm_td_")
            or not separator
            or len(identifier) != 32
            or not secret
        ):
            return None
        if any(character not in "0123456789abcdef" for character in identifier):
            return None
        return identifier

    @staticmethod
    async def live_record(session, owner_id, identifier):
        return await session.scalar(
            select(TrustedDevice)
            .join(User, User.access_id == TrustedDevice.owner_id)
            .join(AccountSecurity, AccountSecurity.owner_id == TrustedDevice.owner_id)
            .where(
                TrustedDevice.id == identifier,
                TrustedDevice.owner_id == owner_id,
                TrustedDevice.auth_revision == User.auth_revision,
                User.is_active.is_(True),
                AccountSecurity.totp_secret.is_not(None),
                TrustedDevice.revoked_at.is_(None),
                TrustedDevice.expires_at > int(time.time()),
            )
        )

    async def session_proof(self, session, owner, proof):
        if (
            proof.owner_id != owner.access_id
            or proof.auth_revision != owner.auth_revision
        ):
            raise HTTPException(401, "Account security changed; verify again")
        if proof.passkey_id is not None:
            active = await session.scalar(
                select(PasskeyCredential.id).where(
                    PasskeyCredential.id == proof.passkey_id,
                    PasskeyCredential.owner_id == owner.access_id,
                    PasskeyCredential.revoked_at.is_(None),
                )
            )
            if active is None:
                raise HTTPException(401, "Passkey revoked; verify again")
        if proof.fresh_factor or proof.device_id is None:
            return None
        if await self.live_record(session, owner.access_id, proof.device_id) is None:
            raise HTTPException(
                401,
                "Authenticator or recovery code required",
                headers={"X-BSM-MFA": "required"},
            )
        return proof.device_id

    async def validate(self, owner_id, token, *, touch=False):
        identifier = self.identifier(token)
        if identifier is None:
            return None
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            device = await self.live_record(session, owner_id, identifier)
            if device is None or not hmac.compare_digest(
                device.token_digest, hashlib.sha256(token.encode()).hexdigest()
            ):
                return None
            if touch and device.last_used_at < now - 60:
                await session.execute(
                    update(TrustedDevice)
                    .where(
                        TrustedDevice.id == identifier,
                        TrustedDevice.revoked_at.is_(None),
                    )
                    .values(last_used_at=now)
                )
            return device

    @staticmethod
    async def enrolled_factors(session, owner_id):
        factor = await session.get(AccountSecurity, owner_id)
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
        return bool(factor and factor.totp_secret), has_passkey

    async def verify_factor(self, owner_id, revision, otp, token):
        async with self.context.storage.transaction() as session:
            owner = await session.scalar(select(User).where(User.access_id == owner_id))
            if owner is None or not owner.is_active or owner.auth_revision != revision:
                return None
            enabled, has_passkey = await self.enrolled_factors(session, owner_id)
        if not enabled and has_passkey:
            raise HTTPException(
                401,
                "Sign in or verify with your passkey",
                headers={"X-BSM-MFA": "passkey"},
            )
        if not enabled:
            return FactorProof(owner_id, revision, False)
        # An explicitly supplied OTP must pass; do not silently fall back to trust.
        if otp:
            valid = await self.context.session_service.verify_factor(owner_id, otp)
            if not valid:
                return None
            previous = await self.validate(owner_id, token) if token else None
            return FactorProof(
                owner_id, revision, True, previous.id if previous else None
            )
        device = await self.validate(owner_id, token, touch=True)
        if device is not None and device.auth_revision == revision:
            return FactorProof(owner_id, revision, False, device.id)
        return None

    async def remember(self, proof: FactorProof, request):
        if not proof.fresh_factor:
            return None
        now = int(time.time())
        identifier = uuid4().hex
        token = f"bsm_td_{identifier}.{secrets.token_urlsafe(32)}"
        async with self.context.storage.write_lock:
            async with self.context.storage.transaction() as session:
                # Acquire the same owner's database write lock even on SQLite.
                result = await session.execute(
                    update(User)
                    .where(
                        User.access_id == proof.owner_id,
                        User.auth_revision == proof.auth_revision,
                        User.is_active.is_(True),
                    )
                    .values(auth_revision=User.auth_revision)
                )
                factor = await session.get(AccountSecurity, proof.owner_id)
                if result.rowcount != 1 or not factor or not factor.totp_secret:
                    raise HTTPException(401, "Account security changed; verify again")
                if proof.device_id is not None:
                    await session.execute(
                        update(TrustedDevice)
                        .where(
                            TrustedDevice.id == proof.device_id,
                            TrustedDevice.owner_id == proof.owner_id,
                        )
                        .values(revoked_at=now)
                    )
                active = list(
                    await session.scalars(
                        select(TrustedDevice)
                        .where(
                            TrustedDevice.owner_id == proof.owner_id,
                            TrustedDevice.auth_revision == proof.auth_revision,
                            TrustedDevice.revoked_at.is_(None),
                            TrustedDevice.expires_at > now,
                        )
                        .order_by(TrustedDevice.created_at, TrustedDevice.id)
                        .limit(MAX_DEVICES + 1)
                    )
                )
                # Bounded replacement avoids consuming a one-use code only to reject login.
                for old in active[: max(0, len(active) - MAX_DEVICES + 1)]:
                    old.revoked_at = now
                revoked_ids = [
                    old.id for old in active[: max(0, len(active) - MAX_DEVICES + 1)]
                ]
                if proof.device_id:
                    revoked_ids.append(proof.device_id)
                if revoked_ids:
                    await session.execute(
                        update(LoginSession)
                        .where(
                            LoginSession.owner_id == proof.owner_id,
                            LoginSession.verified_device_id.in_(revoked_ids),
                        )
                        .values(verified_at=0, verified_device_id=None)
                    )
                device = TrustedDevice(
                    id=identifier,
                    owner_id=proof.owner_id,
                    token_digest=hashlib.sha256(token.encode()).hexdigest(),
                    auth_revision=proof.auth_revision,
                    **self.context.session_service.client_metadata(request),
                    created_at=now,
                    last_used_at=now,
                    expires_at=now + TRUST_DAYS * 86400,
                )
                session.add(device)
                self.context.session_service.add_event(
                    session,
                    proof.owner_id,
                    "trusted_device_remembered",
                    {"device_id": identifier, "replaced_device_ids": revoked_ids},
                )
        await self.context.session_service.publish(
            proof.owner_id, "trusted_device_remembered"
        )
        return token, device.expires_at

    async def list(self, owner_id, current_token=None):
        current = await self.validate(owner_id, current_token)
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            revision = await session.scalar(
                select(User.auth_revision).where(User.access_id == owner_id)
            )
            rows = list(
                await session.scalars(
                    select(TrustedDevice)
                    .where(TrustedDevice.owner_id == owner_id)
                    .order_by(
                        case(
                            (
                                (TrustedDevice.revoked_at.is_(None))
                                & (TrustedDevice.expires_at > now)
                                & (TrustedDevice.auth_revision == revision),
                                0,
                            ),
                            else_=1,
                        ),
                        TrustedDevice.created_at.desc(),
                        TrustedDevice.id.desc(),
                    )
                    .limit(100)
                )
            )
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "user_agent": row.user_agent,
                    "ip_address": row.ip_address,
                    "created_at": row.created_at,
                    "last_used_at": row.last_used_at,
                    "expires_at": row.expires_at,
                    "status": (
                        "revoked"
                        if row.revoked_at is not None
                        else (
                            "expired"
                            if row.expires_at <= now
                            else (
                                "invalidated"
                                if row.auth_revision != revision
                                else "active"
                            )
                        )
                    ),
                    "current": current is not None and current.id == row.id,
                }
                for row in rows
            ]

    async def revoke(self, owner_id, *, identifier=None, except_id=None):
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            if identifier is not None:
                record = await session.get(TrustedDevice, identifier)
                if record is None or record.owner_id != owner_id:
                    raise HTTPException(404, "Remembered device not found")
            query = update(TrustedDevice).where(
                TrustedDevice.owner_id == owner_id, TrustedDevice.revoked_at.is_(None)
            )
            if identifier:
                query = query.where(TrustedDevice.id == identifier)
            if except_id:
                query = query.where(TrustedDevice.id != except_id)
            affected = select(TrustedDevice.id).where(
                TrustedDevice.owner_id == owner_id
            )
            if identifier:
                affected = affected.where(TrustedDevice.id == identifier)
            if except_id:
                affected = affected.where(TrustedDevice.id != except_id)
            await session.execute(
                update(LoginSession)
                .where(
                    LoginSession.owner_id == owner_id,
                    LoginSession.verified_device_id.in_(affected),
                )
                .values(verified_at=0, verified_device_id=None)
            )
            result = await session.execute(query.values(revoked_at=now))
            self.context.session_service.add_event(
                session,
                owner_id,
                "trusted_devices_revoked",
                {
                    "count": result.rowcount,
                    "device_id": identifier,
                    "mode": "one" if identifier else "others" if except_id else "all",
                },
            )
        await self.context.session_service.publish(owner_id, "trusted_devices_revoked")
        return result.rowcount
