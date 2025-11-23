"""
Database models for Bedrock Server Manager.

This module defines the SQLAlchemy ORM models representing the application's
database schema. It includes models for users, settings, servers, plugins,
registration tokens, players, and audit logs.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
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


class Setting(Base):
    """
    Represents a configuration setting.

    Settings can be global or specific to a server.

    Attributes:
        id (int): The primary key.
        key (str): The configuration key (dot-notation).
        value (JSON): The configuration value, stored as JSON.
        server_id (int, optional): Foreign key to the :class:`Server` table.
            If NULL, this is a global setting.
        server (Server): Relationship to the associated server (if any).
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), index=True)
    value = Column(JSON)
    server_id = Column(Integer, ForeignKey("servers.id"))

    server = relationship("Server", back_populates="settings")


class Server(Base):
    """
    Represents a registered Bedrock server.

    Attributes:
        id (int): The primary key.
        server_name (str): The unique name of the server.
        config (JSON): Stores server-specific configuration (legacy or supplementary).
        settings (List[Setting]): Relationship to the server's specific settings.
    """

    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    server_name = Column(String(255), unique=True, index=True)
    config = Column(JSON)

    settings = relationship("Setting", back_populates="server")


class Plugin(Base):
    """
    Represents a registered plugin.

    Attributes:
        id (int): The primary key.
        plugin_name (str): The unique name of the plugin.
        config (JSON): The plugin's configuration data.
    """

    __tablename__ = "plugins"

    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String(255), unique=True, index=True)
    config = Column(JSON)


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

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True)
    role = Column(String(50))
    expires = Column(Integer)


class Player(Base):
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

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255))
    details = Column(JSON)

    user = relationship("User")
