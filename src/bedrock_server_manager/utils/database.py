import json
from datetime import datetime
from typing import Any, Dict, Optional, cast

import aiofiles
from sqlalchemy import Connection, delete, inspect, select
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db import models
from ..db.database import Database

# Define the order of migration/restore to respect foreign key constraints
MODELS_TO_MANAGE = [
    models.User,
    models.Server,
    models.ServerBan,
    models.Setting,
    models.Plugin,
    models.RegistrationToken,
    models.Player,
    models.AuditLog,
]


def default_serializer(obj: Any) -> str:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


async def get_current_db_revision(engine: Optional[AsyncEngine]) -> Optional[str]:
    """Retrieves the current Alembic revision from the database asynchronously."""
    if not engine:
        return None

    def _get_rev(connection: Connection) -> Optional[str]:
        inspector = inspect(connection)
        if inspector.has_table("alembic_version"):
            from sqlalchemy import text

            result = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            return cast(Optional[str], result)
        return None

    async with engine.connect() as connection:
        return cast(Optional[str], await connection.run_sync(_get_rev))


async def get_backup_metadata(input_path: str) -> Dict[str, Any]:
    """Reads the metadata from a backup JSON file asynchronously."""
    async with aiofiles.open(input_path, "r") as f:
        content = await f.read()
        backup_data = json.loads(content)
        return dict(backup_data.get("_metadata", {}))


async def backup_database(db: Database, output_path: str) -> None:
    """Backups all database records to a JSON file asynchronously."""
    backup_data: Dict[str, Any] = {}

    current_rev = await get_current_db_revision(db.engine)
    if current_rev:
        backup_data["_metadata"] = {"alembic_version": current_rev}

    async with db.session_manager() as session:
        for model in MODELS_TO_MANAGE:
            model_name = model.__name__
            result = await session.execute(select(model))
            records = result.scalars().all()
            model_data = []
            for record in records:
                record_dict = {
                    c.name: getattr(record, c.name) for c in record.__table__.columns
                }
                model_data.append(record_dict)
            backup_data[model_name] = model_data

    async with aiofiles.open(output_path, "w") as f:
        await f.write(json.dumps(backup_data, default=default_serializer, indent=4))


async def restore_database(db: Database, backup_data: Dict[str, Any]) -> None:
    """Restores database records from a dictionary payload asynchronously. Wipes existing data!"""
    async with db.session_manager() as session:
        # 1. Delete existing data (reverse order to respect foreign keys)
        for model in reversed(MODELS_TO_MANAGE):
            await session.execute(delete(model))

        # 2. Insert new data
        for model in MODELS_TO_MANAGE:
            model_name = model.__name__
            if model_name not in backup_data:
                continue

            records_data = backup_data[model_name]
            new_objects = []
            for record_dict in records_data:
                # Convert ISO datetime strings back to datetime objects
                for col in getattr(model, "__table__").columns:
                    col_name = col.name
                    if col_name in record_dict and record_dict[col_name] is not None:
                        import sqlalchemy

                        is_datetime = (
                            isinstance(col.type, sqlalchemy.types.DateTime)
                            or type(col.type).__name__ == "DateTime"
                        )

                        if is_datetime:
                            if isinstance(record_dict[col_name], str):
                                try:
                                    record_dict[col_name] = datetime.fromisoformat(
                                        record_dict[col_name]
                                    )
                                except ValueError:
                                    pass

                new_objects.append(model(**record_dict))

            session.add_all(new_objects)
        await session.commit()
