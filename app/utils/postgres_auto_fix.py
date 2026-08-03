from sqlalchemy import text
from sqlalchemy.engine import Engine
from app import db


def is_postgresql(engine: Engine) -> bool:
    return engine.url.get_backend_name().startswith("postgresql")


def repair_postgres_schema():
    if not is_postgresql(db.engine):
        return

    statements = [
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS bidding_starts_at TIMESTAMP",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS bidding_ends_at TIMESTAMP",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS completion_ends_at TIMESTAMP",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verification_mode VARCHAR(20)",
        "ALTER TABLE elite_sprint_session ALTER COLUMN created_by DROP NOT NULL",
        "ALTER TABLE submission ADD COLUMN IF NOT EXISTS sprint_session_id INTEGER",
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) DEFAULT \'approved\'',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS golden_stars INTEGER DEFAULT 0',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS penalty_flags INTEGER DEFAULT 0',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS has_active_sprint_penalty BOOLEAN DEFAULT FALSE',
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS task_ids JSONB DEFAULT '[]'",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS daily_tasks JSONB DEFAULT '[]'",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS weekly_tasks JSONB DEFAULT '[]'",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS monthly_tasks JSONB DEFAULT '[]'",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS has_golden_star BOOLEAN DEFAULT FALSE",
        "ALTER TABLE elite_sprint_bid ALTER COLUMN task_ids TYPE JSONB USING task_ids::JSONB",
        "ALTER TABLE elite_sprint_bid ALTER COLUMN daily_tasks TYPE JSONB USING daily_tasks::JSONB",
        "ALTER TABLE elite_sprint_bid ALTER COLUMN weekly_tasks TYPE JSONB USING weekly_tasks::JSONB",
        "ALTER TABLE elite_sprint_bid ALTER COLUMN monthly_tasks TYPE JSONB USING monthly_tasks::JSONB",
    ]

    for statement in statements:
        db.session.execute(text(statement))

    db.session.commit()