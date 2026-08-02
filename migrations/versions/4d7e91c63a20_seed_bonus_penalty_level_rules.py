"""seed bonus penalty level rules

Revision ID: 4d7e91c63a20
Revises: 27a9c4b8f501
Create Date: 2026-07-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "4d7e91c63a20"
down_revision = "27a9c4b8f501"
branch_labels = None
depends_on = None


point_rule = sa.table(
    "point_rule",
    sa.column("stream", sa.String),
    sa.column("code", sa.String),
    sa.column("category", sa.String),
    sa.column("title", sa.String),
    sa.column("points", sa.Integer),
)


RULES = [
    ("bonus", "BONUS001", "Achievement", "Daily Top Performer", 20),
    ("bonus", "BONUS002", "Achievement", "Weekly Top Performer", 75),
    ("bonus", "BONUS003", "Achievement", "Monthly Top Performer", 200),
    ("bonus", "BONUS004", "Achievement", "30-Day Attendance", 50),
    ("bonus", "BONUS005", "Achievement", "Helping another ELITE member", 20),
    ("bonus", "BONUS006", "Achievement", "Conducting a technical session", 50),
    ("bonus", "BONUS007", "Achievement", "Open Source Contribution", 100),
    ("bonus", "BONUS008", "Achievement", "Paper Accepted", 300),
    ("bonus", "BONUS009", "Achievement", "Patent Published", 500),
    ("bonus", "BONUS010", "Achievement", "Internship Offer", 300),
    ("bonus", "BONUS011", "Achievement", "Placement Offer (>10 LPA)", 500),
    ("penalty", "PENALTY001", "Activity", "Daily task not updated", -5),
    ("penalty", "PENALTY002", "Activity", "Weekly target missed", -20),
    ("penalty", "PENALTY003", "Activity", "Monthly review absent", -50),
    ("penalty", "PENALTY004", "Activity", "Plagiarism", -100),
    ("penalty", "PENALTY005", "Activity", "Fake submission", -150),
    ("penalty", "PENALTY006", "Activity", "Missing project review", -50),
    ("level", "LEVEL001", "Level", "0-500: Beginner", 0),
    ("level", "LEVEL002", "Level", "501-1,500: Explorer", 501),
    ("level", "LEVEL003", "Level", "1,501-3,000: Innovator", 1501),
    ("level", "LEVEL004", "Level", "3,001-5,000: AI Professional", 3001),
    ("level", "LEVEL005", "Level", "5,001-8,000: ELITE Achiever", 5001),
    ("level", "LEVEL006", "Level", "8,001-12,000: ELITE Champion", 8001),
    ("level", "LEVEL007", "Level", "Above 12,000: Hall of Fame", 12001),
]


def upgrade():
    bind = op.get_bind()
    for stream, code, category, title, points in RULES:
        existing = bind.execute(sa.select(point_rule.c.code).where(point_rule.c.code == code)).first()
        values = {"stream": stream, "category": category, "title": title, "points": points}
        if existing:
            bind.execute(point_rule.update().where(point_rule.c.code == code).values(**values))
        else:
            bind.execute(point_rule.insert().values(code=code, **values))


def downgrade():
    codes = [row[1] for row in RULES]
    op.execute(point_rule.delete().where(point_rule.c.code.in_(codes)))
