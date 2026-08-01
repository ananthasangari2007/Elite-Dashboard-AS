"""add submission date daily uniqueness

Revision ID: 1f8e4c7d2b90
Revises: 9c1a24e6d8b1
Create Date: 2026-07-30 23:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "1f8e4c7d2b90"
down_revision = "9c1a24e6d8b1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("submission", schema=None) as batch_op:
        batch_op.add_column(sa.Column("submission_date", sa.Date(), nullable=True))
        batch_op.create_index(batch_op.f("ix_submission_submission_date"), ["submission_date"], unique=False)

    op.execute("UPDATE submission SET submission_date = DATE(submitted_at) WHERE submission_date IS NULL")

    with op.batch_alter_table("submission", schema=None) as batch_op:
        batch_op.alter_column("submission_date", existing_type=sa.Date(), nullable=False)
        batch_op.create_unique_constraint(
            "uq_submission_student_task_date",
            ["student_id", "task_id", "submission_date"],
        )


def downgrade():
    with op.batch_alter_table("submission", schema=None) as batch_op:
        batch_op.drop_constraint("uq_submission_student_task_date", type_="unique")
        batch_op.drop_index(batch_op.f("ix_submission_submission_date"))
        batch_op.drop_column("submission_date")
