# src/bedrock_server_manager/utils/migration.py
"""
Utilities for running Alembic database schema migrations.
"""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db.database import Database


async def run_migrations_upgrade(db: "Database") -> None:
    """Runs pending Alembic database migrations up to head asynchronously."""
    await asyncio.to_thread(db._run_alembic_upgrade)


async def run_migrations_downgrade(db: "Database", revision: str = "-1") -> None:
    """Runs Alembic database migrations downgrade asynchronously."""
    await asyncio.to_thread(db._run_alembic_downgrade, revision)
