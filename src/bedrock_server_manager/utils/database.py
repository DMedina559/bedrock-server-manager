import json
from datetime import datetime
from typing import Any, Dict, Optional, cast

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

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


def get_current_db_revision(engine: Optional[Engine]) -> Optional[str]:
    """Retrieves the current Alembic revision from the database."""
    if not engine:
        return None
    with engine.connect() as connection:
        inspector = inspect(connection)
        if inspector.has_table("alembic_version"):
            from sqlalchemy import text

            result = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            return cast(Optional[str], result)
    return None


def get_backup_metadata(input_path: str) -> Dict[str, Any]:
    """Reads the metadata from a backup JSON file."""
    with open(input_path, "r") as f:
        backup_data = json.load(f)
        return dict(backup_data.get("_metadata", {}))


def backup_database(db: Database, output_path: str) -> None:
    """Backups all database records to a JSON file."""
    backup_data: Dict[str, Any] = {}

    current_rev = get_current_db_revision(db.engine)
    if current_rev:
        backup_data["_metadata"] = {"alembic_version": current_rev}

    with db.session_manager() as session:  # type: ignore
        for model in MODELS_TO_MANAGE:
            model_name = model.__name__
            records = session.query(model).all()
            model_data = []
            for record in records:
                record_dict = {
                    c.name: getattr(record, c.name) for c in record.__table__.columns
                }
                model_data.append(record_dict)
            backup_data[model_name] = model_data

    with open(output_path, "w") as f:
        json.dump(backup_data, f, default=default_serializer, indent=4)


def restore_database(db: Database, backup_data: Dict[str, Any]) -> None:
    """Restores database records from a dictionary payload. Wipes existing data!"""
    with db.session_manager() as session:  # type: ignore
        # 1. Delete existing data (reverse order to respect foreign keys)
        for model in reversed(MODELS_TO_MANAGE):
            session.query(model).delete()

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
                        # Heuristic: if it looks like an ISO format string and the column is DateTime
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

            session.bulk_save_objects(new_objects)
        session.commit()
