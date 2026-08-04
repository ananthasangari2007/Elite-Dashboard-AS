"""add sprint_mode to elite_sprint_session

Revision ID: a1b2c3d4e5f6
Revises: f977847837d7
Create Date: 2026-08-04 07:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f977847837d7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("elite_sprint_session", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sprint_mode", sa.String(length=20), nullable=False, server_default="overall"))
        batch_op.create_index(batch_op.f("ix_elite_sprint_session_sprint_mode"), ["sprint_mode"], unique=False)

    op.execute("UPDATE elite_sprint_session SET sprint_mode = 'overall' WHERE sprint_mode IS NULL")

    with op.batch_alter_table("elite_sprint_session", schema=None) as batch_op:
        batch_op.alter_column("sprint_mode", existing_type=sa.String(length=20), nullable=False, server_default=None)


def downgrade():
    with op.batch_alter_table("elite_sprint_session", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_elite_sprint_session_sprint_mode"))
        batch_op.drop_column("sprint_mode")
