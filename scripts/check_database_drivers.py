"""Smoke-test installed async and migration drivers without database connections."""

import asyncio

from sqlalchemy.engine import make_url

from bedrock_server_manager.db.database import Database


async def main():
    for scheme in ("sqlite", "postgresql", "mysql", "mariadb"):
        url = (
            "sqlite://" if scheme == "sqlite" else f"{scheme}://localhost/driver_check"
        )
        database = Database(url)
        try:
            database.initialize()
            make_url(database._get_sync_db_url()).get_dialect().import_dbapi()
        finally:
            await database.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
