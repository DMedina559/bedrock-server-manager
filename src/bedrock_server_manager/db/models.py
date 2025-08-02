"""Database models for Bedrock Server Manager."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
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
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), index=True)
    value = Column(JSON)
    server_id = Column(Integer, ForeignKey("servers.id"))

    server = relationship("Server", back_populates="settings")


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    server_name = Column(String(255), unique=True, index=True)
    config = Column(JSON)

    settings = relationship("Setting", back_populates="server")


class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String(255), unique=True, index=True)
    config = Column(JSON)


class RegistrationToken(Base):
    __tablename__ = "registration_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True)
    role = Column(String(50))
    expires = Column(Integer)


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    player_name = Column(String(80), unique=True, index=True)
    xuid = Column(String(20), unique=True, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255))
    details = Column(JSON)

    user = relationship("User")
