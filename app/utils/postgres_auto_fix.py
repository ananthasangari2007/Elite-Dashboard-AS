from app import db


def repair_postgres_schema():
    statements = [
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS bidding_starts_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS bidding_ends_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS completion_ends_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verified BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verification_mode VARCHAR(20)",
        "ALTER TABLE submission ADD COLUMN IF NOT EXISTS sprint_session_id INTEGER REFERENCES elite_sprint_session(id)",
        "ALTER TABLE user ADD COLUMN IF NOT EXISTS approval_status VARCHAR(30) NOT NULL DEFAULT 'approved'",
        "ALTER TABLE user ADD COLUMN IF NOT EXISTS golden_stars INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE user ADD COLUMN IF NOT EXISTS penalty_flags INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE user ADD COLUMN IF NOT EXISTS has_active_sprint_penalty BOOLEAN NOT NULL DEFAULT FALSE",
    ]

    for statement in statements:
        db.session.execute(db.text(statement))

    db.session.commit()