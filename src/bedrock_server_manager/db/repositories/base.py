"""
Base repository class for database operations.
"""

from typing import Any


class BaseRepository:
    """Base repository providing database session management helpers."""

    def __init__(self, db: Any = None):
        self.db = db
