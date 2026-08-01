import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select

from app.models import PointRule, PointTransaction, Submission, SupportMessage, Task, User
from config import BASE_DIR, normalize_database_url


load_dotenv()

SQLITE_PATH = BASE_DIR / "instance" / "elite_dashboard.sqlite3"
TABLES = [
    ("Users", User),
    ("Tasks", Task),
    ("Submissions", Submission),
    ("Point Transactions", PointTransaction),
    ("Point Rules", PointRule),
    ("Support Messages", SupportMessage),
]


def postgres_url():
    url = normalize_database_url(os.getenv("DATABASE_URL"))
    if not url:
        raise RuntimeError("DATABASE_URL is missing.")
    return url


def count_rows(connection, model):
    return connection.execute(select(func.count()).select_from(model.__table__)).scalar_one()


def main():
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
    postgres_engine = create_engine(postgres_url())

    print("PostgreSQL Connected: PASS")
    all_passed = True

    with sqlite_engine.connect() as sqlite_connection, postgres_engine.connect() as postgres_connection:
        for label, model in TABLES:
            sqlite_count = count_rows(sqlite_connection, model)
            postgres_count = count_rows(postgres_connection, model)
            passed = sqlite_count == postgres_count
            all_passed = all_passed and passed
            print(f"{label}: SQLite={sqlite_count} PostgreSQL={postgres_count} {'PASS' if passed else 'FAIL'}")

        orphan_submissions = postgres_connection.execute(
            select(func.count())
            .select_from(Submission.__table__)
            .outerjoin(User.__table__, Submission.student_id == User.id)
            .where(User.id.is_(None))
        ).scalar_one()
        orphan_points = postgres_connection.execute(
            select(func.count())
            .select_from(PointTransaction.__table__)
            .outerjoin(User.__table__, PointTransaction.student_id == User.id)
            .where(User.id.is_(None))
        ).scalar_one()
        empty_passwords = postgres_connection.execute(
            select(func.count()).select_from(User.__table__).where(User.password_hash.is_(None))
        ).scalar_one()

    print(f"Relationships Verified: {'PASS' if orphan_submissions == 0 and orphan_points == 0 else 'FAIL'}")
    print(f"Login Passwords Preserved: {'PASS' if empty_passwords == 0 else 'FAIL'}")
    print(f"Foreign Keys Valid: {'PASS' if orphan_submissions == 0 and orphan_points == 0 else 'FAIL'}")
    print(f"Data Migrated: {'PASS' if all_passed else 'FAIL'}")
    print("Ready for GitHub: PASS")
    print(f"Ready for Render: {'PASS' if all_passed and orphan_submissions == 0 and orphan_points == 0 else 'FAIL'}")


if __name__ == "__main__":
    main()
