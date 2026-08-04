"""elite sprint verification v2

Revision ID: f977847837d7
Revises: c1dedf6a7303
Create Date: 2026-08-02 15:46:04.791754

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f977847837d7'
down_revision = 'c1dedf6a7303'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS sprint_verification_result (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            planned_task_ids TEXT,
            submitted_task_ids TEXT,
            missing_task_ids TEXT,
            penalty_points INTEGER DEFAULT 0,
            earned_golden_star BOOLEAN DEFAULT FALSE NOT NULL,
            verified_at TIMESTAMP NOT NULL
        )
    """)
    op.execute('CREATE INDEX IF NOT EXISTS ix_sprint_verification_result_session_id ON sprint_verification_result (session_id)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_sprint_verification_result_student_id ON sprint_verification_result (student_id)')

    op.execute('ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS task_ids JSON NOT NULL DEFAULT \'[]\'::json')

    op.execute('ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS bidding_starts_at TIMESTAMP')
    op.execute('ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS bidding_ends_at TIMESTAMP')
    op.execute('ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS completion_ends_at TIMESTAMP')
    op.execute('ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE NOT NULL')
    op.execute('ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP')
    op.execute('ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS verification_mode VARCHAR(20)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_elite_sprint_session_bidding_ends_at ON elite_sprint_session (bidding_ends_at)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_elite_sprint_session_bidding_starts_at ON elite_sprint_session (bidding_starts_at)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_elite_sprint_session_completion_ends_at ON elite_sprint_session (completion_ends_at)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_elite_sprint_session_is_verified ON elite_sprint_session (is_verified)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_elite_sprint_session_verified ON elite_sprint_session (verified)')

    op.execute('ALTER TABLE submission ADD COLUMN IF NOT EXISTS sprint_session_id INTEGER')
    op.execute('CREATE INDEX IF NOT EXISTS ix_submission_sprint_session_id ON submission (sprint_session_id)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_submission_student_task_date_status ON submission (student_id, task_id, submission_date, status)')
    op.execute('ALTER TABLE submission ADD CONSTRAINT fk_submission_sprint_session_id_elite_sprint_session FOREIGN KEY (sprint_session_id) REFERENCES elite_sprint_session (id)')

    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS golden_stars INTEGER DEFAULT 0 NOT NULL')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS penalty_flags INTEGER DEFAULT 0 NOT NULL')


def downgrade():
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS penalty_flags')
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS golden_stars')

    op.execute('ALTER TABLE submission DROP CONSTRAINT IF EXISTS fk_submission_sprint_session_id_elite_sprint_session')
    op.execute('DROP INDEX IF EXISTS ix_submission_sprint_session_id')
    op.execute('DROP INDEX IF EXISTS ix_submission_student_task_date_status')
    op.execute('ALTER TABLE submission DROP COLUMN IF EXISTS sprint_session_id')

    op.execute('DROP INDEX IF EXISTS ix_elite_sprint_session_verified')
    op.execute('DROP INDEX IF EXISTS ix_elite_sprint_session_is_verified')
    op.execute('DROP INDEX IF EXISTS ix_elite_sprint_session_completion_ends_at')
    op.execute('DROP INDEX IF EXISTS ix_elite_sprint_session_bidding_starts_at')
    op.execute('DROP INDEX IF EXISTS ix_elite_sprint_session_bidding_ends_at')
    op.execute('ALTER TABLE elite_sprint_session DROP COLUMN IF EXISTS verification_mode')
    op.execute('ALTER TABLE elite_sprint_session DROP COLUMN IF EXISTS verified_at')
    op.execute('ALTER TABLE elite_sprint_session DROP COLUMN IF EXISTS verified')
    op.execute('ALTER TABLE elite_sprint_session DROP COLUMN IF EXISTS completion_ends_at')
    op.execute('ALTER TABLE elite_sprint_session DROP COLUMN IF EXISTS bidding_ends_at')
    op.execute('ALTER TABLE elite_sprint_session DROP COLUMN IF EXISTS bidding_starts_at')

    op.execute('ALTER TABLE elite_sprint_bid DROP COLUMN IF EXISTS task_ids')

    op.execute('DROP INDEX IF EXISTS ix_sprint_verification_result_student_id')
    op.execute('DROP INDEX IF EXISTS ix_sprint_verification_result_session_id')
    op.execute('DROP TABLE IF EXISTS sprint_verification_result')
