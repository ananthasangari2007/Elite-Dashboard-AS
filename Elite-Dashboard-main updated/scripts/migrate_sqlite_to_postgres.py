import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import PointRule, PointTransaction, Submission, SupportMessage, Task, User
from config import BASE_DIR, normalize_database_url


load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("sqlite-to-postgres")

SQLITE_PATH = BASE_DIR / "instance" / "elite_dashboard.sqlite3"
TABLES = [User, Task, PointRule, Submission, SupportMessage, PointTransaction]


def sqlite_url(path):
    return f"sqlite:///{path}"


def postgres_url():
    url = normalize_database_url(os.getenv("DATABASE_URL"))
    if not url:
        raise RuntimeError("DATABASE_URL is missing. Add PostgreSQL DATABASE_URL to .env first.")
    if not url.startswith("postgresql://"):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL.")
    return url


def row_exists(connection, table, row_id):
    result = connection.execute(select(table.c.id).where(table.c.id == row_id)).first()
    return result is not None


def copy_table(source_connection, target_connection, model):
    table = model.__table__
    started = time.perf_counter()
    copied = 0
    skipped = 0

    LOGGER.info("Migrating table: %s", table.name)
    rows = source_connection.execute(select(table)).mappings().all()

    for row in rows:
        row_data = {column.name: row.get(column.name) for column in table.columns}
        if row_exists(target_connection, table, row_data["id"]):
            skipped += 1
            continue
        target_connection.execute(table.insert().values(**row_data))
        copied += 1

    elapsed = time.perf_counter() - started
    LOGGER.info("%s copied=%s skipped=%s elapsed=%.2fs", table.name, copied, skipped, elapsed)
    return copied, skipped


def reset_postgres_sequences(connection):
    for model in TABLES:
        table_name = model.__table__.name
        connection.execute(
            text(
                f'SELECT setval(pg_get_serial_sequence(:table_name, \'id\'), '
                f'COALESCE((SELECT MAX(id) FROM "{table_name}"), 1), '
                f'COALESCE((SELECT MAX(id) FROM "{table_name}"), 0) > 0)'
            ),
            {"table_name": table_name},
        )


def main():
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {SQLITE_PATH}")

    source_engine = create_engine(sqlite_url(SQLITE_PATH))
    target_engine = create_engine(postgres_url())

    LOGGER.info("SQLite source: %s", SQLITE_PATH)
    LOGGER.info("PostgreSQL target configured.")

    try:
        with source_engine.connect() as source_connection:
            with target_engine.begin() as target_connection:
                for model in TABLES:
                    copy_table(source_connection, target_connection, model)
                reset_postgres_sequences(target_connection)
        LOGGER.info("Migration committed successfully.")
    except IntegrityError:
        LOGGER.exception("Integrity error. Migration rolled back.")
        raise
    except SQLAlchemyError:
        LOGGER.exception("Database error. Migration rolled back.")
        raise


if __name__ == "__main__":
    main()
