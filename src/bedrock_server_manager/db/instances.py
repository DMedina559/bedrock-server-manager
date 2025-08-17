from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database import Database

_db_instance: Database | None = None


def set_db_instance(db_instance: Database):
    """
    Sets the global database instance.

    Args:
        db_instance (Database): The database instance to set.
    """
    global _db_instance
    _db_instance = db_instance


def get_db_instance() -> Database:
    """
    Gets the global database instance.

    Returns:
        Database: The global database instance.

    Raises:
        RuntimeError: If the database instance has not been set.
    """
    if _db_instance is None:
        # To maintain backward compatibility for now, we can fall back to the default instance.
        # In the future, this should raise a RuntimeError.
        from .database import _db_instance as default_db_instance
        return default_db_instance
        # raise RuntimeError("Database instance has not been set.")
    return _db_instance
