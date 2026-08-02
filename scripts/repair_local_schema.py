"""
Repair local SQLite schema for Elite Sprint features.

Adds missing columns to the local SQLite database (instance/elite_dashboard.sqlite3)
without deleting existing student, task, submission, or point data.

This script is idempotent - safe to run multiple times.
"""

import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "instance" / "elite_dashboard.sqlite3"

# Expected columns per table: {table_name: {column_name: column_definition}}
EXPECTED_COLUMNS = {
    "elite_sprint_session": {
        "bidding_starts_at": "DATETIME",
        "bidding_ends_at": "DATETIME",
        "completion_ends_at": "DATETIME",
        "verified": "BOOLEAN DEFAULT 0",
        "verified_at": "DATETIME",
        "verification_mode": "TEXT",
    },
    "user": {
        "approval_status": "TEXT DEFAULT 'approved'",
        "golden_stars": "INTEGER DEFAULT 0",
        "penalty_flags": "INTEGER DEFAULT 0",
        "has_active_sprint_penalty": "BOOLEAN DEFAULT 0",
    },
    "submission": {
        "sprint_session_id": "INTEGER",
    },
}


def get_existing_columns(conn, table_name):
    """Return a set of existing column names for the given table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def table_exists(conn, table_name):
    """Return True if the table exists in the database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def add_missing_columns(conn, table_name, expected_columns):
    """Add missing columns to a table. Returns list of added column names."""
    if not table_exists(conn, table_name):
        print(f"[SKIP] Table '{table_name}' does not exist. Skipping.")
        return []

    existing = get_existing_columns(conn, table_name)
    added = []

    for column_name, column_definition in expected_columns.items():
        if column_name in existing:
            print(f"[OK] Column '{table_name}.{column_name}' already exists.")
            continue

        try:
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )
            added.append(column_name)
            print(f"[ADDED] Column '{table_name}.{column_name}' added successfully.")
        except sqlite3.Error as exc:
            print(f"[ERROR] Failed to add column '{table_name}.{column_name}': {exc}")

    return added


def main():
    if not DB_PATH.exists():
        print(f"[ERROR] SQLite database not found: {DB_PATH}")
        sys.exit(1)

    print(f"[INFO] Connecting to database: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        for table_name, expected_columns in EXPECTED_COLUMNS.items():
            add_missing_columns(conn, table_name, expected_columns)

        conn.commit()
        print("[INFO] Schema repair completed successfully.")
    except sqlite3.Error as exc:
        print(f"[ERROR] Database error: {exc}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()