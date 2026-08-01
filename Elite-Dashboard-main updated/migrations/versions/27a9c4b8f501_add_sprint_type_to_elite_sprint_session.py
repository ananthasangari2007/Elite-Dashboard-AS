"""add sprint type to elite sprint session

Revision ID: 27a9c4b8f501
Revises: 1f8e4c7d2b90
Create Date: 2026-07-31 00:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "27a9c4b8f501"
down_revision = "1f8e4c7d2b90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("elite_sprint_session", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sprint_type", sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f("ix_elite_sprint_session_sprint_type"), ["sprint_type"], unique=False)

    op.execute("UPDATE elite_sprint_session SET sprint_type = 'overall' WHERE sprint_type IS NULL")

    with op.batch_alter_table("elite_sprint_session", schema=None) as batch_op:
        batch_op.alter_column("sprint_type", existing_type=sa.String(length=20), nullable=False)


def downgrade():
    with op.batch_alter_table("elite_sprint_session", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_elite_sprint_session_sprint_type"))
        batch_op.drop_column("sprint_type")
