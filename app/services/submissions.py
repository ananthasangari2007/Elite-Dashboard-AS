from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.models import Submission, Task, User


def current_submission_date():
    return datetime.utcnow().date()


def can_submit_task_on_date(student_id, task_id, target_date=None):
    target_date = target_date or current_submission_date()
    rows = (
        Submission.query.filter_by(
            student_id=student_id,
            task_id=task_id,
            submission_date=target_date,
        ).all()
    )
    if not rows:
        return True, None

    statuses = {row.status for row in rows}
    if "approved" in statuses:
        return False, "You already completed this task today. It will reopen automatically at 12:00 AM."
    if "waiting_approval" in statuses or "pending" in statuses:
        return False, "A pending submission exists for this task today. Please wait for admin review."
    return True, None


def submitted_task_ids_for_date(student_id, target_date=None):
    target_date = target_date or current_submission_date()
    rows = (
        Submission.query.filter_by(student_id=student_id, submission_date=target_date)
        .filter(Submission.status.in_(["waiting_approval", "approved", "pending"]))
        .with_entities(Submission.task_id)
        .all()
    )
    return {row.task_id for row in rows}


def has_submitted_task_on_date(student_id, task_id, target_date=None):
    allowed, _ = can_submit_task_on_date(student_id, task_id, target_date)
    return not allowed


def current_daily_streak(student_id):
    rows = (
        db.session.query(Submission.submission_date)
        .filter(
            Submission.student_id == student_id,
            Submission.status == "approved",
            Submission.submission_date.isnot(None),
        )
        .group_by(Submission.submission_date)
        .order_by(Submission.submission_date.desc())
        .all()
    )
    approved_dates = {row.submission_date for row in rows}
    if not approved_dates:
        return 0

    cursor = current_submission_date()
    if cursor not in approved_dates:
        cursor = cursor - timedelta(days=1)
        if cursor not in approved_dates:
            return 0

    streak = 0
    while cursor in approved_dates:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def top_daily_streaks(limit=5):
    students = User.query.filter_by(role="student").order_by(User.name.asc()).all()
    rows = [
        {
            "name": student.name,
            "department": student.department or "Not set",
            "streak": current_daily_streak(student.id),
        }
        for student in students
    ]
    rows.sort(key=lambda row: (-row["streak"], row["name"]))
    return rows[:limit]


def dashboard_submission_analytics():
    today = current_submission_date()
    week_start = today - timedelta(days=today.weekday())
    today_query = Submission.query.filter(Submission.submission_date == today)
    today_count = today_query.count()
    unique_students_today = (
        db.session.query(func.count(func.distinct(Submission.student_id)))
        .filter(Submission.submission_date == today)
        .scalar()
        or 0
    )
    active_task = (
        db.session.query(Task.title, func.count(Submission.id).label("submission_count"))
        .join(Submission, Submission.task_id == Task.id)
        .filter(Submission.submission_date == today)
        .group_by(Task.id, Task.title)
        .order_by(func.count(Submission.id).desc(), Task.title.asc())
        .first()
    )
    week_submissions = Submission.query.filter(Submission.submission_date >= week_start).count()
    week_students = (
        db.session.query(func.count(func.distinct(Submission.student_id)))
        .filter(Submission.submission_date >= week_start)
        .scalar()
        or 0
    )
    return {
        "today_submissions": today_count,
        "unique_students_today": int(unique_students_today),
        "most_active_daily_task": active_task.title if active_task else "No submissions today",
        "average_submissions_per_student_week": round(week_submissions / week_students, 2) if week_students else 0,
    }
