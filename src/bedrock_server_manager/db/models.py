"""
Database models for Bedrock Server Manager.

This module defines the SQLAlchemy ORM models representing the application's
database schema. It includes models for users, settings, servers, plugins,
registration tokens, players, and audit logs.
"""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import JsonValue
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    """Represent a user in the system."""

    __tablename__ = "users"

    auth_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    access_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=lambda: uuid4().hex
    )

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(80), nullable=True, unique=True, index=True
    )
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True, default="user")
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    theme: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="default"
    )
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Setting(Base):
    """Represent a configuration setting.

    Settings are global configurations for the application.

    :ivar id: The primary key.

    :ivar key: The configuration key (dot-notation).

    :ivar value: The configuration value, stored as JSON.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    value: Mapped[JsonValue] = mapped_column(JSON, nullable=True)


class PluginSetting(Base):
    """Plugin-owned configuration, retained independently of plugin registration."""

    __tablename__ = "plugin_settings"

    plugin_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    settings: Mapped[dict[str, JsonValue]] = mapped_column(JSON, nullable=False)


class Server(Base):
    """Represent a registered Bedrock server."""

    __tablename__ = "servers"

    access_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=lambda: uuid4().hex
    )

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    server_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    installed_version: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="UNKNOWN"
    )
    status: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="UNKNOWN"
    )
    autoupdate: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=False
    )
    autostart: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=False
    )
    target_version: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="UNKNOWN"
    )
    custom: Mapped[JsonValue] = mapped_column(JSON, nullable=True, default=dict)

    bans: Mapped[list["ServerBan"]] = relationship("ServerBan", back_populates="server")


class ServerBan(Base):
    """Represent a player banned from a specific Bedrock server."""

    __tablename__ = "server_bans"

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    server_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("servers.id"), nullable=True, index=True
    )
    player_name: Mapped[str | None] = mapped_column(
        String(80), nullable=True, index=True
    )
    xuid: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banned_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    server: Mapped["Server"] = relationship("Server", back_populates="bans")


class Plugin(Base):
    """Represent a registered plugin."""

    __tablename__ = "plugins"

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    plugin_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RegistrationToken(Base):
    """Represent a token used for user registration.

    :ivar id: The primary key.

    :ivar token: The unique registration token string.

    :ivar role: The role that will be assigned to the user who registers with this token.

    :ivar expires: Timestamp (unix epoch?) indicating when the token expires.
    """

    __tablename__ = "registration_tokens"

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    token: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expires: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Player(Base):
    """Represent a known player.

    :ivar id: The primary key.

    :ivar player_name: The player's gamertag/name.

    :ivar xuid: The player's unique Xbox User ID.
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    player_name: Mapped[str | None] = mapped_column(
        String(80), nullable=True, unique=True, index=True
    )
    xuid: Mapped[str | None] = mapped_column(
        String(20), nullable=True, unique=True, index=True
    )


class DiagnosticHistoryRow(Base):
    """Bounded sanitized diagnostic history, separate from domain and audit records."""

    __tablename__ = "diagnostic_history"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    subsystem: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(160), nullable=True, index=True
    )
    owner: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    operation_id: Mapped[str | None] = mapped_column(
        String(160), nullable=True, index=True
    )
    record: Mapped[dict[str, JsonValue]] = mapped_column(JSON, nullable=False)


class AuditLog(Base):
    """Represent an entry in the audit log."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=lambda: datetime.now(timezone.utc)
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[JsonValue] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship("User")


class Schedule(Base):
    """Task definitions and durable coalescing/retry cursor."""

    __tablename__ = "schedules"
    schedule_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    legacy_server: Mapped[str | None] = mapped_column(String(160), nullable=True)


class ScheduleRun(Base):
    """Bounded per-attempt outcomes, independent of archive catalogs."""

    __tablename__ = "schedule_runs"
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    slot: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class AccessRevision(Base):
    """Monotonic revision for committed authorization mutations."""

    __tablename__ = "access_revision"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AccountServerAccess(Base):
    """Absent accounts keep existing unrestricted role access."""

    __tablename__ = "account_server_access"
    owner_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    assigned_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ServerAccessGrant(Base):
    """Grants refer to immutable identities, never reusable names or row IDs."""

    __tablename__ = "server_access_grants"
    owner_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class IntegrationToken(Base):
    """Only a digest is stored. Opaque credentials are shown once on creation."""

    __tablename__ = "integration_tokens"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    server_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    last_used_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revoked_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LoginSession(Base):
    """Revocable login family; JWT renewal never extends its absolute expiry."""

    __tablename__ = "login_sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_at: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    verified_at: Mapped[int] = mapped_column(Integer, nullable=False)
    revoked_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AccountSecurity(Base):
    """Encrypted TOTP material and one-use recovery digests, never raw codes."""

    __tablename__ = "account_security"
    owner_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_until: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    recovery_hashes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AuthThrottle(Base):
    """Persistent fixed-window budgets shared across workers and restarts."""

    __tablename__ = "auth_throttle"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)


class AuthSecurityEvent(Base):
    __tablename__ = "auth_security_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
