"""
Database models for Bedrock Server Manager.

This module defines the SQLAlchemy ORM models representing the application's
database schema. It includes models for users, settings, servers, plugins,
registration tokens, players, and audit logs.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base  # type: ignore


class User(Base):  # type: ignore
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

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(50), default="user")
    last_seen = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    theme = Column(String(50), default="default")
    is_active = Column(Boolean, default=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)


class Setting(Base):  # type: ignore
    """
    Represents a configuration setting.

    Settings are global configurations for the application.

    Attributes:
        id (int): The primary key.
        key (str): The configuration key (dot-notation).
        value (JSON): The configuration value, stored as JSON.
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), index=True)
    value = Column(JSON)


class Server(Base):  # type: ignore
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

    id = Column(Integer, primary_key=True, index=True)
    server_name = Column(String(255), unique=True, index=True)
    installed_version = Column(String(50), default="UNKNOWN")
    status = Column(String(50), default="UNKNOWN")
    autoupdate = Column(Boolean, default=False)
    autostart = Column(Boolean, default=False)
    target_version = Column(String(50), default="UNKNOWN")
    custom = Column(JSON, default={})

    bans = relationship("ServerBan", back_populates="server")


class ServerBan(Base):  # type: ignore
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

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), index=True)
    player_name = Column(String(80), index=True)
    xuid = Column(String(20), index=True)
    reason = Column(String(255), nullable=True)
    banned_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    server = relationship("Server", back_populates="bans")


class Plugin(Base):  # type: ignore
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

    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String(255), unique=True, index=True)
    enabled = Column(Boolean, default=False)
    version = Column(String(50), nullable=True)
    author = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)


class RegistrationToken(Base):  # type: ignore
    """
    Represents a token used for user registration.

    Attributes:
        id (int): The primary key.
        token (str): The unique registration token string.
        role (str): The role that will be assigned to the user who registers with this token.
        expires (int): Timestamp (unix epoch?) indicating when the token expires.
    """

    __tablename__ = "registration_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True)
    role = Column(String(50))
    expires = Column(Integer)


class Player(Base):  # type: ignore
    """
    Represents a known player.

    Attributes:
        id (int): The primary key.
        player_name (str): The player's gamertag/name.
        xuid (str): The player's unique Xbox User ID.
    """

    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    player_name = Column(String(80), unique=True, index=True)
    xuid = Column(String(20), unique=True, index=True)


class AuditLog(Base):  # type: ignore
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

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255))
    details = Column(JSON)

    user = relationship("User")
