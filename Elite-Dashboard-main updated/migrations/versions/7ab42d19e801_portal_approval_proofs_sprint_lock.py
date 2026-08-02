"""portal approval proofs sprint lock

Revision ID: 7ab42d19e801
Revises: 4d7e91c63a20
Create Date: 2026-08-01 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "7ab42d19e801"
down_revision = "4d7e91c63a20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("approval_status", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("has_active_sprint_penalty", sa.Boolean(), nullable=True))
        batch_op.create_index(batch_op.f("ix_user_approval_status"), ["approval_status"], unique=False)
        batch_op.create_index(batch_op.f("ix_user_has_active_sprint_penalty"), ["has_active_sprint_penalty"], unique=False)

    op.execute("UPDATE \"user\" SET approval_status = 'approved' WHERE approval_status IS NULL")
    op.execute("UPDATE \"user\" SET has_active_sprint_penalty = false WHERE has_active_sprint_penalty IS NULL")

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column("approval_status", existing_type=sa.String(length=30), nullable=False)
        batch_op.alter_column("has_active_sprint_penalty", existing_type=sa.Boolean(), nullable=False)

    with op.batch_alter_table("submission", schema=None) as batch_op:
        batch_op.add_column(sa.Column("proof_url", sa.String(length=700), nullable=True))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_submission_approved_at"), ["approved_at"], unique=False)
        batch_op.drop_constraint("uq_submission_student_task_date", type_="unique")
        batch_op.create_index("ix_submission_student_task_date_status", ["student_id", "task_id", "submission_date", "status"], unique=False)

    op.execute("UPDATE submission SET approved_at = reviewed_at WHERE status = 'approved' AND approved_at IS NULL")
    op.execute("UPDATE submission SET proof_url = github_link WHERE proof_url IS NULL AND github_link IS NOT NULL AND github_link != ''")
    op.execute("UPDATE submission SET proof_url = drive_link WHERE proof_url IS NULL AND drive_link IS NOT NULL AND drive_link != ''")

    with op.batch_alter_table("elite_sprint_bid", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_locked", sa.Boolean(), nullable=True))
        batch_op.create_index(batch_op.f("ix_elite_sprint_bid_is_locked"), ["is_locked"], unique=False)

    op.execute("UPDATE elite_sprint_bid SET is_locked = true WHERE is_locked IS NULL")

    with op.batch_alter_table("elite_sprint_bid", schema=None) as batch_op:
        batch_op.alter_column("is_locked", existing_type=sa.Boolean(), nullable=False)


def downgrade():
    with op.batch_alter_table("elite_sprint_bid", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_elite_sprint_bid_is_locked"))
        batch_op.drop_column("is_locked")

    with op.batch_alter_table("submission", schema=None) as batch_op:
        batch_op.drop_index("ix_submission_student_task_date_status")
        batch_op.create_unique_constraint("uq_submission_student_task_date", ["student_id", "task_id", "submission_date"])
        batch_op.drop_index(batch_op.f("ix_submission_approved_at"))
        batch_op.drop_column("approved_at")
        batch_op.drop_column("proof_url")

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_has_active_sprint_penalty"))
        batch_op.drop_index(batch_op.f("ix_user_approval_status"))
        batch_op.drop_column("has_active_sprint_penalty")
        batch_op.drop_column("approval_status")
