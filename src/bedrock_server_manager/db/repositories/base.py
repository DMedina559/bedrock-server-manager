"""
Base repository class for database operations.
"""

from ..database import Database


class BaseRepository:
    """Base repository providing database session management helpers."""

    def __init__(self, db: Database | None = None):
        self.db = db
