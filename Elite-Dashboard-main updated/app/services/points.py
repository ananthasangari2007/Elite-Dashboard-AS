from datetime import datetime

from sqlalchemy import func

from app import db
from app.models import PointTransaction, User


BADGE_LEVELS = [
    (12001, "🏆 Hall of Fame", "Above 12,000"),
    (8001, "👑 ELITE Champion", "8,001-12,000"),
    (5001, "💎 ELITE Achiever", "5,001-8,000"),
    (3001, "🤖 AI Professional", "3,001-5,000"),
    (1501, "🚀 Innovator", "1,501-3,000"),
    (501, "🧭 Explorer", "501-1,500"),
    (0, "🌱 Beginner", "0-500"),
]


def badge_for_points(points):
    points = int(points or 0)
    for minimum, label, range_text in BADGE_LEVELS:
        if points >= minimum:
            return {"label": label, "range": range_text, "minimum": minimum}
    return {"label": "🌱 Beginner", "range": "0-500", "minimum": 0}


def record_award(student_id, task_id, points, reason, approved_by):
    transaction = PointTransaction.award(
        student_id=student_id,
        task_id=task_id,
        points=points,
        reason=reason,
        approved_by=approved_by,
    )
    db.session.add(transaction)
    return transaction


def record_bonus(student_id, points, reason, approved_by):
    transaction = PointTransaction.award(
        student_id=student_id,
        task_id=None,
        points=points,
        reason=reason,
        approved_by=approved_by,
    )
    db.session.add(transaction)
    return transaction


def record_penalty(student_id, points, reason, approved_by):
    transaction = PointTransaction.penalty(
        student_id=student_id,
        points=points,
        reason=reason,
        approved_by=approved_by,
    )
    db.session.add(transaction)
    return transaction


def overall_points_query():
    return (
        db.session.query(
            User.id.label("student_id"),
            User.name.label("student_name"),
            func.coalesce(func.sum(PointTransaction.points), 0).label("overall_points"),
        )
        .outerjoin(PointTransaction, PointTransaction.student_id == User.id)
        .filter(User.role == "student")
        .group_by(User.id, User.name)
    )


def monthly_points_query(year=None, month=None):
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    return (
        db.session.query(
            User.id.label("student_id"),
            User.name.label("student_name"),
            func.coalesce(func.sum(PointTransaction.points), 0).label("monthly_points"),
        )
        .outerjoin(
            PointTransaction,
            (PointTransaction.student_id == User.id)
            & (PointTransaction.created_at >= start)
            & (PointTransaction.created_at < end),
        )
        .filter(User.role == "student")
        .group_by(User.id, User.name)
    )


def leaderboard(limit=10):
    rows = overall_points_query().order_by(db.desc("overall_points"), User.name.asc()).limit(limit).all()
    ranked = []
    for index, row in enumerate(rows, start=1):
        points = int(row.overall_points or 0)
        badge = badge_for_points(points)

        ranked.append(
            {
                "rank": index,
                "name": row.student_name,
                "points": points,
                "badge": badge["label"],
                "badge_range": badge["range"],
            }
        )
    return ranked


def total_points_awarded():
    return int(db.session.query(func.coalesce(func.sum(PointTransaction.points), 0)).scalar() or 0)
