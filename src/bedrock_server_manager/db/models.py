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
    """
    Represents a user in the system.

    Attributes:
        id (int): The primary key.
        username (str): The unique username of the user.
        hashed_password (str): The hashed password.
        role (str): The user's role (e.g., 'user', 'admin'). Defaults to 'user'.
        last_seen (datetime): The timestamp when the user was last active.
        theme (str): The user's preferred UI theme. Defaults to 'default'.
        is_active (bool): Whether the user account is active. Defaults to True.
        full_name (str, optional): The user's full name.
        email (str, optional): The user's email address.
    """

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
    """
    Represents a configuration setting.

    Settings are global configurations for the application.

    Attributes:
        id (int): The primary key.
        key (str): The configuration key (dot-notation).
        value (JSON): The configuration value, stored as JSON.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True, index=True
    )
    key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    value: Mapped[JsonValue] = mapped_column(JSON, nullable=True)


class Server(Base):
    """
    Represents a registered Bedrock server.

    Attributes:
        id (int): The primary key.
        server_name (str): The unique name of the server.
        installed_version (str): The currently installed version of the server.
        status (str): The current status of the server.
        autoupdate (bool): Whether the server should automatically update.
        autostart (bool): Whether the server should automatically start.
        target_version (str): The target version to install/update to.
        custom (JSON): Stores custom server-specific configuration.
    """

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
    """
    Represents a player banned from a specific Bedrock server.

    Attributes:
        id (int): The primary key.
        server_id (int): Foreign key to the :class:`Server` table.
        player_name (str): The name of the banned player.
        xuid (str): The Xbox User ID of the banned player.
        reason (str): The reason for the ban.
        banned_at (datetime): The date and time when the ban was issued.
        server (Server): Relationship to the associated server.
    """

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
    """
    Represents a registered plugin.

    Attributes:
        id (int): The primary key.
        plugin_name (str): The unique name of the plugin.
        enabled (bool): Whether the plugin is enabled.
        version (str): The plugin's version.
        author (str): The plugin's author.
        description (str): The plugin's description.
    """

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
    """
    Represents a token used for user registration.

    Attributes:
        id (int): The primary key.
        token (str): The unique registration token string.
        role (str): The role that will be assigned to the user who registers with this token.
        expires (int): Timestamp (unix epoch?) indicating when the token expires.
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
    """
    Represents a known player.

    Attributes:
        id (int): The primary key.
        player_name (str): The player's gamertag/name.
        xuid (str): The player's unique Xbox User ID.
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
    """
    Represents an entry in the audit log.

    Records significant actions taken by users within the system.

    Attributes:
        id (int): The primary key.
        timestamp (datetime): When the action occurred.
        user_id (int): Foreign key to the :class:`User` who performed the action.
        action (str): A string describing the action type (e.g., "server_start").
        details (JSON): Additional details about the action (e.g., specific parameters).
        user (User): Relationship to the user who performed the action.
    """

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
