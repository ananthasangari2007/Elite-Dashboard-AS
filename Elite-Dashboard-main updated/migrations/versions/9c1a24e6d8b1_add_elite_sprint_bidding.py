"""add elite sprint bidding

Revision ID: 9c1a24e6d8b1
Revises: b6463543bae2
Create Date: 2026-07-30 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "9c1a24e6d8b1"
down_revision = "b6463543bae2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "elite_sprint_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sprint_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("elite_sprint_session", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_elite_sprint_session_created_by"), ["created_by"], unique=False)
        batch_op.create_index(batch_op.f("ix_elite_sprint_session_end_time"), ["end_time"], unique=False)
        batch_op.create_index(batch_op.f("ix_elite_sprint_session_sprint_date"), ["sprint_date"], unique=False)
        batch_op.create_index(batch_op.f("ix_elite_sprint_session_start_time"), ["start_time"], unique=False)
        batch_op.create_index(batch_op.f("ix_elite_sprint_session_status"), ["status"], unique=False)

    op.create_table(
        "elite_sprint_bid",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("daily_count", sa.Integer(), nullable=False),
        sa.Column("weekly_count", sa.Integer(), nullable=False),
        sa.Column("monthly_count", sa.Integer(), nullable=False),
        sa.Column("daily_tasks", sa.JSON(), nullable=False),
        sa.Column("weekly_tasks", sa.JSON(), nullable=False),
        sa.Column("monthly_tasks", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["elite_sprint_session.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "student_id", name="uq_elite_sprint_bid_session_student"),
    )
    with op.batch_alter_table("elite_sprint_bid", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_elite_sprint_bid_session_id"), ["session_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_elite_sprint_bid_student_id"), ["student_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_elite_sprint_bid_submitted_at"), ["submitted_at"], unique=False)


def downgrade():
    with op.batch_alter_table("elite_sprint_bid", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_elite_sprint_bid_submitted_at"))
        batch_op.drop_index(batch_op.f("ix_elite_sprint_bid_student_id"))
        batch_op.drop_index(batch_op.f("ix_elite_sprint_bid_session_id"))
    op.drop_table("elite_sprint_bid")

    with op.batch_alter_table("elite_sprint_session", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_elite_sprint_session_status"))
        batch_op.drop_index(batch_op.f("ix_elite_sprint_session_start_time"))
        batch_op.drop_index(batch_op.f("ix_elite_sprint_session_sprint_date"))
        batch_op.drop_index(batch_op.f("ix_elite_sprint_session_end_time"))
        batch_op.drop_index(batch_op.f("ix_elite_sprint_session_created_by"))
    op.drop_table("elite_sprint_session")
