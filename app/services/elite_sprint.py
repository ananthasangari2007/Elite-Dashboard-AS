import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func

from app import db
from app.models import (
    EliteSprintBid,
    EliteSprintBidTask,
    EliteSprintSession,
    Submission,
    Task,
    User,
)


APP_TIMEZONE = os.getenv("ELITE_TIMEZONE", "Asia/Kolkata")
VERIFICATION_WINDOW_HOURS = 15


def sprint_timezone():
    try:
        return ZoneInfo(APP_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_today_sprint():
    today = utc_now().date()
    session = EliteSprintSession.query.filter_by(sprint_date=today).first()
    if not session:
        return None
    now = utc_now()
    start_dt = datetime.combine(session.sprint_date, session.start_time)
    end_dt = datetime.combine(session.sprint_date, session.end_time)
    if start_dt <= now < end_dt:
        return session
    return None


def get_sprint_for_date(sprint_date):
    return EliteSprintSession.query.filter_by(sprint_date=sprint_date).first()


def create_sprint(sprint_date, start_time, end_time):
    existing = EliteSprintSession.query.filter_by(sprint_date=sprint_date).first()
    if existing:
        return None, "A sprint already exists for this date."
    session = EliteSprintSession(
        sprint_date=sprint_date,
        start_time=start_time,
        end_time=end_time,
    )
    db.session.add(session)
    db.session.commit()
    return session, None


def process_expired_sprint_verifications():
    try:
        now = utc_now()
        locked_bids = EliteSprintBid.query.filter(
            EliteSprintBid.is_locked.is_(True),
            EliteSprintBid.is_verified.is_(False),
        ).all()
    except Exception:
        db.session.rollback()
        return
    for bid in locked_bids:
        try:
            if bid.verification_due_at and now < bid.verification_due_at:
                continue
            if not bid.session:
                continue
            session = bid.session
            sprint_end = datetime.combine(session.sprint_date, session.end_time)
            if now < sprint_end:
                continue
            _verify_single_bid(bid)
        except Exception:
            db.session.rollback()
            continue


def _verify_single_bid(bid):
    try:
        session = bid.session
        student = bid.student
        if not session or not student:
            return

        planned_task_ids = {bt.task_id for bt in bid.tasks}

        if not planned_task_ids:
            bid.is_verified = True
            bid.verified_at = datetime.utcnow()
            db.session.commit()
            return

        submitted_task_ids = {
            submission.task_id
            for submission in Submission.query.filter(
                Submission.student_id == bid.student_id,
                Submission.submitted_at >= bid.locked_at,
            ).all()
        }

        missing_ids = planned_task_ids - submitted_task_ids

        if not missing_ids:
            student.golden_stars = (student.golden_stars or 0) + 1
            bid.has_golden_star = True
            bid.is_verified = True
            bid.verified_at = datetime.utcnow()
        else:
            penalty_points = 0
            missing_task_ids_list = []
            for tid in sorted(missing_ids):
                task = Task.query.get(tid)
                if task:
                    penalty_points += task.reward_points
                    missing_task_ids_list.append(str(tid))
            bid.penalty_points = penalty_points
            bid.penalty_reason = ",".join(missing_task_ids_list) if missing_task_ids_list else ""
            bid.has_golden_star = False
            bid.is_verified = True
            bid.verified_at = datetime.utcnow()

        db.session.commit()
    except Exception:
        db.session.rollback()


def get_student_sprint_status(student_id):
    bids = EliteSprintBid.query.filter_by(student_id=student_id).order_by(EliteSprintBid.submitted_at.desc()).all()
    for bid in bids:
        if not bid.session:
            continue
        session = bid.session
        if bid.is_locked:
            if bid.is_verified:
                if bid.has_golden_star:
                    return "Golden Star Earned"
                return "Penalty Applied"
            return "Verification Pending"
        return "Sprint Locked"
    return None


def get_sprint_metrics(session):
    if not session:
        return {
            "locked_students": 0,
            "verified_students": 0,
        }
    locked = EliteSprintBid.query.filter_by(session_id=session.id, is_locked=True).count()
    verified = EliteSprintBid.query.filter_by(session_id=session.id, is_verified=True).count()
    return {
        "locked_students": locked,
        "verified_students": verified,
    }