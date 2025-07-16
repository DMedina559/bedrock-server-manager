"""Database models for Bedrock Server Manager."""

from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    settings = relationship("Setting", back_populates="owner")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, index=True)
    value = Column(JSON)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="settings")
