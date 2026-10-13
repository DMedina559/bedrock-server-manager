"""
Database models for Bedrock Server Manager.

This module defines the SQLAlchemy ORM models representing the application's
database schema. It includes models for users, settings, servers, plugins,
registration tokens, players, and audit logs.
"""

from datetime import datetime, timezone

from pydantic import JsonValue
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
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
