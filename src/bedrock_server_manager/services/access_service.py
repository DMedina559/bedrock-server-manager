"""Persisted credential and resource restrictions beneath the existing role ceiling."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, update

from ..db.models import (
    AccessRevision,
    AccountSecurity,
    AccountServerAccess,
    IntegrationToken,
    Server,
    ServerAccessGrant,
    User,
)
from ..web.authorization import (
    NON_DELEGATABLE,
    PERSONAL_PERMISSIONS,
    SERVER_EVENTS,
    SERVER_PERMISSIONS,
    Authorization,
)
from ..web.schemas import UserResponse
from ..web.schemas.access import (
    AccountServerAccessInfo,
    CreatedIntegrationToken,
    IntegrationTokenInfo,
    ServerGrant,
)

logger = logging.getLogger(__name__)


class AccessService:
    """Authorization reads use committed storage; revocation never depends on JWT expiry."""

    def __init__(self, context):
        self.context = context

    @property
    def policy(self):
        return self.context.plugin_manager.access_policy

    def validate(self, permissions):
        try:
            self.policy.validate(permissions)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @staticmethod
    def token_info(token) -> IntegrationTokenInfo:
        return IntegrationTokenInfo.model_validate(token, from_attributes=True)

    async def _revision(self, session) -> str:
        revision = await session.scalar(
            select(AccessRevision.revision).where(AccessRevision.id == 1)
        )
        return f"{self.policy.revision}:{revision or 0}"

    async def _bump(self, session):
        await session.execute(
            update(AccessRevision)
            .where(AccessRevision.id == 1)
            .values(revision=AccessRevision.revision + 1)
        )

    async def _user(self, session, user_id):
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(404, "Account not found")
        return user

    async def snapshot(
        self,
        user: UserResponse,
        token_id: str | None = None,
        session_id: str | None = None,
    ) -> Authorization | None:
        async with self.context.storage.transaction() as session:
            row = (
                await session.execute(
                    select(
                        User, AccountServerAccess.assigned_only, AccessRevision.revision
                    )
                    .outerjoin(
                        AccountServerAccess,
                        AccountServerAccess.owner_id == User.access_id,
                    )
                    .outerjoin(AccessRevision, AccessRevision.id == 1)
                    .where(User.id == user.id)
                )
            ).first()
            record = row[0] if row else None
            if (
                record is None
                or not record.is_active
                or record.username != user.username
            ):
                return None
            if (
                session_id is not None
                and await self.context.session_service.validate(
                    session_id, record.access_id, touch=False
                )
                is None
            ):
                return None
            factor = await session.get(AccountSecurity, record.access_id)
            mfa_required = bool(
                token_id is None
                and record.role == "admin"
                and self.context.settings.get("security.require_admin_mfa", False)
                and not (factor and factor.totp_secret)
            )
            permission_set = self.policy.resolve(record.role)
            if mfa_required:
                permission_set &= frozenset({"account:read", "sessions:manage"})
            token_servers = None
            if token_id is not None:
                token = await session.get(IntegrationToken, token_id)
                if (
                    token is None
                    or token.owner_id != record.access_id
                    or token.revoked_at is not None
                    or (
                        token.expires_at is not None
                        and token.expires_at <= int(time.time())
                    )
                ):
                    return None
                permission_set &= frozenset(token.permissions) - NON_DELEGATABLE
                token_servers = (
                    None if token.server_ids is None else frozenset(token.server_ids)
                )
            grants = None
            if row[1]:
                rows = (
                    await session.scalars(
                        select(ServerAccessGrant).where(
                            ServerAccessGrant.owner_id == record.access_id
                        )
                    )
                ).all()
                grants = {row.server_id: frozenset(row.permissions) for row in rows}
            if grants is not None or token_servers is not None:
                permission_set &= SERVER_PERMISSIONS | PERSONAL_PERMISSIONS
            servers = {}
            if grants is not None or token_servers is not None:
                identities = (
                    set(grants) if grants is not None else set(token_servers or ())
                )
                if token_servers is not None:
                    identities &= token_servers
                servers = dict(
                    (
                        await session.execute(
                            select(Server.server_name, Server.access_id).where(
                                Server.access_id.in_(identities)
                            )
                        )
                    ).all()
                )
            return Authorization(
                user_id=user.id,
                username=user.username,
                owner_id=record.access_id,
                permissions=permission_set,
                servers=servers,
                grants=grants,
                token_id=token_id,
                session_id=session_id,
                mfa_enrollment_required=mfa_required,
                token_servers=token_servers,
                revision=f"{self.policy.revision}:{row[2] or 0}:{record.role}:{int(mfa_required)}",
            )

    async def server_identities(self) -> dict[str, str]:
        async with self.context.storage.transaction() as session:
            return dict(
                (
                    await session.execute(select(Server.server_name, Server.access_id))
                ).all()
            )

    async def server_identity(self, name: str) -> str | None:
        async with self.context.storage.transaction() as session:
            identity = await session.scalar(
                select(Server.access_id).where(Server.server_name == name)
            )
            return str(identity) if identity is not None else None

    async def authenticate(self, credential: str):
        """Verify an opaque secret once. Subsequent snapshots use only its identifier."""
        try:
            identifier, secret = credential.removeprefix("bsm_it_").split(".", 1)
        except ValueError:
            return None
        if len(identifier) != 32 or len(secret) != 43:
            return None
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            token = await session.get(IntegrationToken, identifier)
            supplied = hashlib.sha256(credential.encode()).hexdigest()
            expected = token.digest if token else "0" * 64
            if (
                not hmac.compare_digest(expected, supplied)
                or token is None
                or token.revoked_at is not None
                or (token.expires_at is not None and token.expires_at <= now)
            ):
                return None
            record = await session.scalar(
                select(User).where(
                    User.access_id == token.owner_id, User.is_active.is_(True)
                )
            )
            if record is None:
                return None
            user = UserResponse.model_validate(record, from_attributes=True)
            # Rate-limited, conditional update avoids writing on every metrics poll.
            if token.last_used_at is None or token.last_used_at <= now - 60:
                await session.execute(
                    update(IntegrationToken)
                    .where(
                        IntegrationToken.id == identifier,
                        (
                            IntegrationToken.last_used_at.is_(None)
                            | (IntegrationToken.last_used_at <= now - 60)
                        ),
                    )
                    .values(last_used_at=now)
                )
        authorization = await self.snapshot(user, identifier)
        return (user, authorization) if authorization is not None else None

    async def list_tokens(self, user_id):
        async with self.context.storage.transaction() as session:
            user = await self._user(session, user_id)
            rows = (
                await session.scalars(
                    select(IntegrationToken)
                    .where(IntegrationToken.owner_id == user.access_id)
                    .order_by(IntegrationToken.created_at, IntegrationToken.id)
                )
            ).all()
            return [self.token_info(token) for token in rows]

    async def create_token(self, actor, payload) -> CreatedIntegrationToken:
        self.validate(payload.permissions)
        requested = frozenset(payload.permissions)
        if requested & NON_DELEGATABLE:
            raise HTTPException(
                422,
                "Identity and access administration cannot be delegated to integration tokens",
            )
        identifier = uuid4().hex
        credential = f"bsm_it_{identifier}.{secrets.token_urlsafe(32)}"
        now = int(time.time())
        async with self.context.storage.transaction() as session:
            user = await self._user(session, actor.id)
            if not requested <= self.policy.resolve(user.role):
                raise HTTPException(
                    403, "Token permissions exceed the account's current role"
                )
            if payload.server_ids is not None:
                known = set((await session.scalars(select(Server.access_id))).all())
                if not set(payload.server_ids) <= known:
                    raise HTTPException(422, "Unknown server identity")
            count = len(
                (
                    await session.scalars(
                        select(IntegrationToken.id).where(
                            IntegrationToken.owner_id == user.access_id,
                            IntegrationToken.revoked_at.is_(None),
                            or_(
                                IntegrationToken.expires_at.is_(None),
                                IntegrationToken.expires_at > now,
                            ),
                        )
                    )
                ).all()
            )
            if count >= 100:
                raise HTTPException(
                    409, "Revoke an unused credential before creating another"
                )
            token = IntegrationToken(
                id=identifier,
                owner_id=user.access_id,
                name=payload.name.strip(),
                digest=hashlib.sha256(credential.encode()).hexdigest(),
                permissions=sorted(requested),
                server_ids=(
                    None
                    if payload.server_ids is None
                    else sorted(set(payload.server_ids))
                ),
                created_at=now,
                expires_at=(
                    None
                    if payload.expires_in_days is None
                    else now + payload.expires_in_days * 86400
                ),
            )
            session.add(token)
            self.context.session_service.add_event(
                session,
                user.access_id,
                "integration_credential_created",
                {"credential_id": identifier, "name": token.name},
            )
            await self.context.storage.audit_log_repo.create_audit_log(
                session,
                actor.id,
                "create_integration_token",
                {"token_id": identifier, "name": token.name},
            )
            await session.flush()
            info = self.token_info(token)
        await self.notify(actor.username, kind="credentials_changed")
        await self.context.session_service.publish(
            user.access_id, "integration_credential_created"
        )
        return CreatedIntegrationToken(token=credential, credential=info)

    async def rotate_token(self, actor, identifier):
        now = int(time.time())
        new_id = uuid4().hex
        credential = f"bsm_it_{new_id}.{secrets.token_urlsafe(32)}"
        async with self.context.storage.transaction() as session:
            owner = await self._user(session, actor.id)
            old = await session.get(IntegrationToken, identifier)
            if (
                old is None
                or old.owner_id != owner.access_id
                or old.revoked_at is not None
                or (old.expires_at is not None and old.expires_at <= now)
            ):
                raise HTTPException(404, "Active credential not found")
            permissions = sorted(
                set(old.permissions) & self.policy.resolve(owner.role) - NON_DELEGATABLE
            )
            if not permissions:
                raise HTTPException(
                    403, "The account no longer grants this credential any permissions"
                )
            replacement = IntegrationToken(
                id=new_id,
                owner_id=owner.access_id,
                name=old.name,
                digest=hashlib.sha256(credential.encode()).hexdigest(),
                permissions=permissions,
                server_ids=old.server_ids,
                created_at=now,
                expires_at=old.expires_at,
            )
            session.add(replacement)
            changed = await session.execute(
                update(IntegrationToken)
                .where(
                    IntegrationToken.id == identifier,
                    IntegrationToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
                .execution_options(synchronize_session=False)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Credential was already rotated or revoked")
            self.context.session_service.add_event(
                session,
                owner.access_id,
                "integration_credential_rotated",
                {"credential_id": new_id, "previous_id": identifier},
            )
            await session.flush()
            info = self.token_info(replacement)
        await self.notify(actor.username, kind="credentials_changed")
        await self.context.session_service.publish(
            owner.access_id, "integration_credential_rotated"
        )
        return CreatedIntegrationToken(token=credential, credential=info)

    async def revoke_token(self, actor, user_id, identifier):
        async with self.context.storage.transaction() as session:
            owner = await self._user(session, user_id)
            token = await session.get(IntegrationToken, identifier)
            if token is None or token.owner_id != owner.access_id:
                raise HTTPException(404, "Credential not found")
            if token.revoked_at is None:
                token.revoked_at = int(time.time())
                self.context.session_service.add_event(
                    session,
                    owner.access_id,
                    "integration_credential_revoked",
                    {"credential_id": identifier},
                )
                await self.context.storage.audit_log_repo.create_audit_log(
                    session,
                    actor.id,
                    "revoke_integration_token",
                    {"token_id": identifier, "user_id": owner.id},
                )
            username = owner.username
        await self.notify(username, kind="credentials_changed")
        await self.context.session_service.publish(
            owner.access_id, "integration_credential_revoked"
        )

    async def get_server_access(self, user_id):
        async with self.context.storage.transaction() as session:
            user = await self._user(session, user_id)
            access = await session.get(AccountServerAccess, user.access_id)
            rows = (
                await session.scalars(
                    select(ServerAccessGrant)
                    .where(ServerAccessGrant.owner_id == user.access_id)
                    .order_by(ServerAccessGrant.server_id)
                )
            ).all()
            return AccountServerAccessInfo(
                user_id=user_id,
                mode="assigned" if access and access.assigned_only else "all",
                grants=[
                    ServerGrant(server_id=row.server_id, permissions=row.permissions)
                    for row in rows
                ],
                policy_revision=await self._revision(session),
            )

    async def set_server_access(self, actor, user_id, payload):
        identities = [grant.server_id for grant in payload.grants]
        if len(identities) != len(set(identities)):
            raise HTTPException(422, "Duplicate server grants")
        for grant in payload.grants:
            self.validate(grant.permissions)
            if "servers:read" not in grant.permissions:
                raise HTTPException(422, "Server grants must include servers:read")
            if not set(grant.permissions) <= SERVER_PERMISSIONS:
                raise HTTPException(
                    422, "Server grants may only contain server capabilities"
                )
        async with self.context.storage.transaction() as session:
            user = await self._user(session, user_id)
            if actor.id == user.id:
                raise HTTPException(
                    409, "Administrators cannot restrict their own access"
                )
            # Keep administration and account recovery global in this phase.
            if user.role == "admin" and payload.mode == "assigned":
                raise HTTPException(
                    409, "Use a moderator or user account for server-specific access"
                )
            known = set((await session.scalars(select(Server.access_id))).all())
            if not set(identities) <= known:
                raise HTTPException(422, "Unknown server identity")
            await session.merge(
                AccountServerAccess(
                    owner_id=user.access_id, assigned_only=payload.mode == "assigned"
                )
            )
            await session.execute(
                delete(ServerAccessGrant).where(
                    ServerAccessGrant.owner_id == user.access_id
                )
            )
            for grant in payload.grants:
                session.add(
                    ServerAccessGrant(
                        owner_id=user.access_id,
                        server_id=grant.server_id,
                        permissions=sorted(set(grant.permissions)),
                    )
                )
            await self._bump(session)
            await self.context.storage.audit_log_repo.create_audit_log(
                session,
                actor.id,
                "set_server_access",
                {"user_id": user_id, "mode": payload.mode, "server_ids": identities},
            )
            username = user.username
        await self.notify(username)
        return await self.get_server_access(user_id)

    async def notify(
        self, username: str | None = None, *, kind: str = "access_changed"
    ):
        manager = getattr(self.context, "_connection_manager", None)
        if manager is None:
            return
        # Delivery is advisory. Committed mutations and one-time secret responses
        # must not fail because an observer disconnected; enforcement reads storage.
        try:
            message = {"type": kind}
            if username:
                await manager.send_to_user(username, message)
            else:
                for client in list(manager.active_connections.values()):
                    await manager.send_to_client(message, client.id)
        except Exception:
            logger.warning(
                "Authorization change notification unavailable", exc_info=True
            )

    async def task_allowed(self, authorization, task_id):
        record = self.context.task_manager.tasks.get(task_id)
        if record is None or record.username != authorization.username:
            return False
        if (
            authorization.token_id is not None
            and record.access_token_id != authorization.token_id
        ):
            return False
        if (
            record.access_owner_id is not None
            and record.access_owner_id != authorization.owner_id
        ):
            return False
        if not set(record.access_permissions) <= authorization.permissions:
            return False
        if authorization.resource_restricted and record.access_server_id is not None:
            names = [
                name
                for name, identity in authorization.servers.items()
                if identity == record.access_server_id
            ]
            if not names or not all(
                authorization.allows(permission, names[0])
                for permission in record.access_permissions
            ):
                return False
        if not authorization.resource_restricted:
            return "tasks:read" in authorization.permissions
        identity = record.access_server_id
        return (
            identity is not None
            and any(
                value == identity and authorization.allows("servers:read", name)
                for name, value in authorization.servers.items()
            )
            and "tasks:read" in authorization.permissions
        )

    async def topic_allowed(self, authorization, topic):
        if topic in SERVER_EVENTS:
            return "servers:read" in authorization.permissions
        if topic == "access-policy":
            return "account:read" in authorization.permissions
        if topic.startswith("task:"):
            return await self.task_allowed(authorization, topic[5:])
        for prefix, capability in (
            ("server_log:", "logs:read"),
            ("resource-monitor:", "servers:read"),
        ):
            if topic.startswith(prefix):
                return authorization.allows(capability, topic.removeprefix(prefix))
        if topic in {"app_log", "app_logs"}:
            return not authorization.resource_restricted and authorization.allows(
                "logs:read_application"
            )
        if topic == "application-metrics":
            return not authorization.resource_restricted and authorization.allows(
                "runtime:metrics"
            )
        # Unknown/plugin/global event payloads have no resource contract. Retain
        # legacy session behavior but never expose them to restricted principals.
        return not authorization.restricted

    async def filter_message(self, authorization, data):
        if not isinstance(data, dict):
            return data if not authorization.restricted else None
        if data.get("type") == "security_event":
            return (
                data
                if authorization.token_id is None
                and data.get("owner_id") == authorization.owner_id
                and authorization.allows("sessions:manage")
                else None
            )
        if data.get("type") in {
            "access_changed",
            "policy_changed",
            "credentials_changed",
        }:
            return data
        topic = data.get("topic")
        if not topic:
            protocol = not data.get("data") and (
                data.get("status") == "error"
                or data.get("message") == "Authenticated successfully"
                or str(data.get("message", "")).startswith(
                    ("Subscribed to topic '", "Unsubscribed from topic '")
                )
            )
            return data if not authorization.restricted or protocol else None
        if (
            data.get("status") == "error"
            and data.get("message") == "Topic access denied"
            and data.get("data") is None
        ):
            return data
        if (
            topic.startswith("task:")
            and not authorization.restricted
            and topic[5:] not in self.context.task_manager.tasks
        ):
            # Legacy trusted in-process task managers may publish to their owner
            # without using AppContext's TaskManager. Restricted principals cannot.
            return data
        if not await self.topic_allowed(authorization, topic):
            return None
        if topic in SERVER_EVENTS and authorization.restricted:
            payload = data.get("data", {})
            payload = (
                payload.get("result", payload) if isinstance(payload, dict) else {}
            )
            name = payload.get("server_name") if isinstance(payload, dict) else None
            if not name or not authorization.allows("servers:read", name):
                return None
        return data
