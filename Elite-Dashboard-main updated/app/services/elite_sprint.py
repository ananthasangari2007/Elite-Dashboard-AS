import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func

from app import db
from app.models import EliteSprintBid, EliteSprintSession, Task, User


APP_TIMEZONE = os.getenv("ELITE_TIMEZONE", "Asia/Kolkata")


def sprint_timezone():
    try:
        return ZoneInfo(APP_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_datetime_to_utc(value):
    local_value = value.replace(tzinfo=sprint_timezone())
    return local_value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_datetime_to_local(value):
    if not value:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(sprint_timezone())


def latest_session():
    close_expired_sprints()
    return EliteSprintSession.query.order_by(EliteSprintSession.created_at.desc()).first()


def close_expired_sprints():
    now = utc_now()
    expired = EliteSprintSession.query.filter(
        EliteSprintSession.status == "active",
        EliteSprintSession.end_time <= now,
    ).all()
    if not expired:
        return 0
    for session in expired:
        session.status = "closed"
    db.session.commit()
    return len(expired)


def get_active_session():
    close_expired_sprints()
    now = utc_now()
    return (
        EliteSprintSession.query.filter(
            EliteSprintSession.status == "active",
            EliteSprintSession.start_time <= now,
            EliteSprintSession.end_time > now,
        )
        .order_by(EliteSprintSession.end_time.asc())
        .first()
    )


def sprint_leaderboard(session_id=None, limit=None):
    query = (
        db.session.query(
            EliteSprintBid,
            User.name.label("student_name"),
            User.department.label("department"),
            (
                EliteSprintBid.daily_count
                + EliteSprintBid.weekly_count
                + EliteSprintBid.monthly_count
            ).label("total_tasks"),
        )
        .join(User, User.id == EliteSprintBid.student_id)
    )
    if session_id:
        query = query.filter(EliteSprintBid.session_id == session_id)
    rows = query.order_by(
        (
            EliteSprintBid.daily_count
            + EliteSprintBid.weekly_count
            + EliteSprintBid.monthly_count
        ).desc(),
        EliteSprintBid.submitted_at.asc(),
    )
    if limit:
        rows = rows.limit(limit)

    leaderboard = []
    for index, row in enumerate(rows.all(), start=1):
        total = int(row.total_tasks or 0)
        leaderboard.append(
            {
                "rank": index,
                "student_name": row.student_name,
                "department": row.department or "Not set",
                "total_tasks": total,
                "badge": participation_badge(index, total),
                "bid": row.EliteSprintBid,
            }
        )
    return leaderboard


def participation_badge(rank, total):
    if rank == 1:
        return "Sprint Champion"
    if rank <= 3:
        return "Podium Finisher"
    if total >= 10:
        return "High Commitment"
    return "Sprint Participant"


def sprint_metrics(session):
    student_count = User.query.filter_by(role="student").count()
    if not session:
        return {
            "participants": 0,
            "daily": 0,
            "weekly": 0,
            "monthly": 0,
            "highest_bidder": "No bids yet",
            "participation": 0,
        }

    totals = db.session.query(
        func.count(EliteSprintBid.id),
        func.coalesce(func.sum(EliteSprintBid.daily_count), 0),
        func.coalesce(func.sum(EliteSprintBid.weekly_count), 0),
        func.coalesce(func.sum(EliteSprintBid.monthly_count), 0),
    ).filter(EliteSprintBid.session_id == session.id).one()
    leaders = sprint_leaderboard(session.id, limit=1)
    participants = int(totals[0] or 0)
    return {
        "participants": participants,
        "daily": int(totals[1] or 0),
        "weekly": int(totals[2] or 0),
        "monthly": int(totals[3] or 0),
        "highest_bidder": leaders[0]["student_name"] if leaders else "No bids yet",
        "participation": round((participants / student_count) * 100, 2) if student_count else 0,
    }


def active_task_ids_by_type():
    rows = Task.query.filter_by(status="active").with_entities(Task.id, Task.task_code, Task.task_type).all()
    grouped = {"daily": set(), "weekly": set(), "monthly": set()}
    all_ids = set()
    for task_id, task_code, task_type in rows:
        values = {str(task_id)}
        if task_code:
            values.add(task_code.strip().upper())
        all_ids.update(values)
        if task_type in grouped:
            grouped[task_type].update(values)
    return grouped, all_ids
