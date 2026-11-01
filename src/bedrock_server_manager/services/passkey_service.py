"""Passkey ceremonies, atomic challenge consumption and verified factor proofs."""

from __future__ import annotations

import asyncio
import secrets
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import case, delete, func, select, update

from ..db.models import (
    AccountSecurity,
    LoginSession,
    PasskeyChallenge,
    PasskeyCredential,
    User,
)
from ..utils.threads import run_in_thread
from .trusted_device_service import FactorProof
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


class PasskeyService:
    def __init__(self, context):
        self.context = context
        self._verification_slots = asyncio.Semaphore(4)

    async def _verify(self, function, **kwargs):
        async with self._verification_slots:
            return await run_in_thread(function, **kwargs)

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
            await session.execute(
                update(User)
                .where(User.access_id == owner_id)
                .values(auth_revision=User.auth_revision)
            )
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
                    "userVerification": "required",
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
            consumed = await session.execute(
                delete(PasskeyChallenge).where(
                    PasskeyChallenge.id == challenge_row.id,
                    PasskeyChallenge.expires_at >= now,
                )
            )
            if consumed.rowcount != 1:
                raise HTTPException(401, "Passkey challenge already used")

        try:
            verified = await self._verify(
                verify_registration_response,
                credential=payload.credential,
                expected_challenge=expected_challenge,
                expected_rp_id=expected_rp_id,
                allowed_origins=allowed_origins,
                require_user_verification=True,
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
        default_name = (
            self.context.session_service.client_metadata(request)["name"] or "Passkey"
        )
        passkey_name = (payload.name or default_name).strip()[:100] or "Passkey"
        passkey_id = uuid4().hex

        async with self.context.storage.transaction() as session:
            await session.execute(
                update(User)
                .where(User.access_id == owner_id)
                .values(auth_revision=User.auth_revision)
            )
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
            keep_session_id = getattr(request.state, "session_id", None)
            await self.context.session_service.advance_auth_revision(
                session, owner_id, keep_session_id
            )
            await self.context.session_service.revoke_in_transaction(
                session, owner_id, keep_session_id
            )
            if keep_session_id:
                await session.execute(
                    update(LoginSession)
                    .where(
                        LoginSession.id == keep_session_id,
                        LoginSession.owner_id == owner_id,
                    )
                    .values(
                        factor_verified=True, authentication_method="passkey-enrollment"
                    )
                )
            self.context.session_service.add_event(
                session,
                owner_id,
                "passkey_registered",
                {"passkey_id": passkey_id, "name": passkey_name},
            )
            info = self._passkey_info(row)
        await self.context.session_service.close_revoked(owner_id)
        await self.context.session_service.publish(owner_id, "passkey_registered")
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
            await session.execute(
                update(User)
                .where(User.access_id == owner_id)
                .values(auth_revision=User.auth_revision)
            )
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
            await self.context.session_service.advance_auth_revision(session, owner_id)
            row.revoked_at = now
            self.context.session_service.add_event(
                session,
                owner_id,
                "passkey_revoked",
                {"passkey_id": passkey_id, "name": row.name},
            )
        await self.context.session_service.publish(owner_id, "passkey_revoked")

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
                "userVerification": "required",
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
            consumed = await session.execute(
                delete(PasskeyChallenge).where(
                    PasskeyChallenge.id == challenge_row.id,
                    PasskeyChallenge.expires_at >= now,
                )
            )
            if consumed.rowcount != 1:
                raise HTTPException(401, "Passkey challenge already used")

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
            owner_revision = owner.auth_revision

        try:
            verified = await self._verify(
                verify_authentication_response,
                credential=credential,
                expected_challenge=expected_challenge,
                expected_rp_id=expected_rp_id,
                allowed_origins=allowed_origins,
                public_key_b64=public_key_b64,
                stored_sign_count=stored_sign_count,
                require_user_verification=True,
            )
        except PasskeyCounterRegressionError as error:
            async with self.context.storage.transaction() as session:
                self.context.session_service.add_event(
                    session,
                    owner_access_id,
                    "passkey_clone_detected",
                    {"passkey_id": passkey_pk},
                )
            await self.context.session_service.publish(
                owner_access_id, "passkey_clone_detected"
            )
            raise HTTPException(
                401, "Passkey signature counter regression detected"
            ) from error
        except WebAuthnError as error:
            raise HTTPException(401, "Passkey authentication failed") from error

        async with self.context.storage.transaction() as session:
            await session.execute(
                update(User)
                .where(User.access_id == owner_access_id)
                .values(auth_revision=User.auth_revision)
            )
            current_owner = await session.scalar(
                select(User)
                .where(User.access_id == owner_access_id, User.is_active.is_(True))
                .with_for_update()
            )
            current_passkey = await session.get(PasskeyCredential, passkey_pk)
            if (
                current_owner is None
                or current_owner.auth_revision != owner_revision
                or current_passkey is None
                or current_passkey.revoked_at is not None
            ):
                raise HTTPException(401, "Passkey authentication failed")
            if (
                stored_sign_count > 0 or verified.sign_count > 0
            ) and verified.sign_count <= current_passkey.sign_count:
                self.context.session_service.add_event(
                    session,
                    owner_access_id,
                    "passkey_clone_detected",
                    {"passkey_id": passkey_pk},
                )
                counter_regression = True
            else:
                counter_regression = False
            if not counter_regression:
                current_passkey.sign_count = verified.sign_count
                current_passkey.last_used_at = now
                current_passkey.backup_eligible = verified.backup_eligible
                current_passkey.backup_state = verified.backup_state
        if counter_regression:
            await self.context.session_service.publish(
                owner_access_id, "passkey_clone_detected"
            )
            raise HTTPException(401, "Passkey signature counter regression detected")
        return current_owner, current_passkey

    async def complete_passkey_login(self, payload, request) -> tuple[str, FactorProof]:
        peer = request.client.host if request.client else ""
        await self.context.session_service.throttle("", peer, "passkey_login")
        owner, passkey = await self._consume_and_verify_assertion(
            challenge_id=payload.challenge_id,
            credential=payload.credential,
            purpose="login",
            expected_owner_id=None,
            request=request,
        )
        async with self.context.storage.transaction() as session:
            self.context.session_service.add_event(
                session,
                owner.access_id,
                "passkey_login",
                {"passkey_id": passkey.id, "name": passkey.name},
            )
        await self.context.session_service.authentication_succeeded(
            owner.username, "passkey_login"
        )
        await self.context.session_service.publish(owner.access_id, "passkey_login")
        return str(owner.username), FactorProof(
            owner.access_id, owner.auth_revision, True, passkey_id=passkey.id
        )

    async def verify_recent_passkey(
        self, user, identifier: str, payload, request
    ) -> int:
        peer = request.client.host if request.client else ""
        await self.context.session_service.throttle(user.username, peer, "verify")
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
            await session.execute(
                update(User)
                .where(User.access_id == owner_id)
                .values(auth_revision=User.auth_revision)
            )
            current = await session.scalar(
                select(User).where(User.access_id == owner_id).with_for_update()
            )
            if (
                current is None
                or not current.is_active
                or current.auth_revision != revision
            ):
                raise HTTPException(401, "Account security changed; verify again")
            await self.context.trusted_device_service.session_proof(
                session,
                current,
                FactorProof(owner_id, revision, True, passkey_id=passkey.id),
            )
            result = await session.execute(
                update(LoginSession)
                .where(
                    LoginSession.id == identifier,
                    LoginSession.owner_id == owner_id,
                    LoginSession.revoked_at.is_(None),
                    LoginSession.expires_at > now,
                    LoginSession.last_seen_at
                    > now - self.context.session_service.idle_seconds(),
                )
                .values(verified_at=now, verified_device_id=None, factor_verified=True)
            )
            if result.rowcount != 1:
                raise HTTPException(401, "Session no longer active")
            self.context.session_service.add_event(
                session,
                owner_id,
                "passkey_verified",
                {"session_id": identifier, "passkey_id": passkey.id},
            )
        await self.context.session_service.authentication_succeeded(
            user.username, "verify"
        )
        await self.context.session_service.publish(owner_id, "passkey_verified")
        return now
