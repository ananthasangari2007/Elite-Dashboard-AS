from sqlalchemy import text
from app import db


def repair_postgres_schema():
    statements = [
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS bidding_starts_at TIMESTAMP",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS bidding_ends_at TIMESTAMP",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS completion_ends_at TIMESTAMP",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verification_mode VARCHAR(20)",
        "ALTER TABLE submission ADD COLUMN IF NOT EXISTS sprint_session_id INTEGER",
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) DEFAULT \'approved\'',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS golden_stars INTEGER DEFAULT 0',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS penalty_flags INTEGER DEFAULT 0',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS has_active_sprint_penalty BOOLEAN DEFAULT FALSE',
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS task_ids TEXT",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS daily_tasks TEXT",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS weekly_tasks TEXT",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS monthly_tasks TEXT",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP",
        "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS has_golden_star BOOLEAN DEFAULT FALSE",
    ]

    for statement in statements:
        db.session.execute(text(statement))

    db.session.commit()