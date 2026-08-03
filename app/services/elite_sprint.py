import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func

from app import db
from app.models import (
    EliteSprintBid,
    EliteSprintBidTask,
    EliteSprintSession,
    PointTransaction,
    SprintVerificationResult,
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


def _to_time(value):
    if value is None:
        return time(0, 0)

    if isinstance(value, time):
        return value

    if isinstance(value, datetime):
        return value.time()

    return value


def normalize_time(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.time()

    if isinstance(value, time):
        return value

    return None


def get_today_sprint():
    today = date.today()
    session = (
        EliteSprintSession.query
        .filter(EliteSprintSession.sprint_date == today)
        .first()
    )

    if not session:
        return None

    start_time = normalize_time(session.start_time)
    end_time = normalize_time(session.end_time)

    if start_time is None or end_time is None:
        return session

    start_dt = datetime.combine(session.sprint_date, start_time)
    end_dt = datetime.combine(session.sprint_date, end_time)

    now = datetime.utcnow()

    if start_dt <= now <= end_dt:
        session.status = "active"
    elif now > end_dt:
        session.status = "closed"
    else:
        session.status = "scheduled"

    db.session.commit()
    return session


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
            sprint_end_time = normalize_time(session.end_time)
            if sprint_end_time is None:
                continue
            sprint_end = datetime.combine(session.sprint_date, sprint_end_time)
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

        submitted_task_ids = {
            submission.task_id
            for submission in Submission.query.filter(
                Submission.student_id == bid.student_id,
                Submission.submitted_at >= bid.locked_at,
            ).all()
        }

        missing_ids = planned_task_ids - submitted_task_ids

        planned_str = ",".join(str(t) for t in sorted(planned_task_ids))
        submitted_str = ",".join(str(t) for t in sorted(submitted_task_ids))
        missing_str = ",".join(str(t) for t in sorted(missing_ids))

        now = datetime.utcnow()

        if not missing_ids:
            student.golden_stars = (student.golden_stars or 0) + 1
            bid.has_golden_star = True
            bid.is_verified = True
            bid.verified_at = now
            verification = SprintVerificationResult(
                session_id=session.id,
                student_id=student.id,
                planned_task_ids=planned_str,
                submitted_task_ids=submitted_str,
                missing_task_ids="",
                penalty_points=0,
                earned_golden_star=True,
                verified_at=now,
            )
            db.session.add(verification)
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
            bid.verified_at = now

            transaction = PointTransaction.penalty(
                student_id=student.id,
                points=penalty_points,
                reason=f"Elite Sprint: missing tasks {missing_str}",
            )
            db.session.add(transaction)
            student.has_active_sprint_penalty = True

            verification = SprintVerificationResult(
                session_id=session.id,
                student_id=student.id,
                planned_task_ids=planned_str,
                submitted_task_ids=submitted_str,
                missing_task_ids=missing_str,
                penalty_points=penalty_points,
                earned_golden_star=False,
                verified_at=now,
            )
            db.session.add(verification)

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


def get_sprint_leaderboard():
    rows = (
        db.session.query(
            User.id.label("student_id"),
            User.name.label("student_name"),
            User.department,
            db.func.coalesce(func.count(EliteSprintBidTask.id), 0).label("total_tasks"),
            db.func.coalesce(
                db.func.sum(db.case((EliteSprintBid.has_golden_star.is_(True), 1), else_=0)), 0
            ).label("golden_stars"),
            db.func.coalesce(
                db.func.sum(db.case((EliteSprintBid.penalty_points > 0, 1), else_=0)), 0
            ).label("penalty_flags"),
        )
        .select_from(EliteSprintBid)
        .join(User, User.id == EliteSprintBid.student_id)
        .outerjoin(EliteSprintBidTask, EliteSprintBidTask.bid_id == EliteSprintBid.id)
        .filter(EliteSprintBid.is_locked.is_(True))
        .group_by(User.id, User.name, User.department)
        .order_by(db.desc("golden_stars"), db.desc("total_tasks"), User.name.asc())
        .all()
    )

    ranked = []
    for index, row in enumerate(rows, start=1):
        total_tasks = int(row.total_tasks or 0)
        golden_stars = int(row.golden_stars or 0)
        penalty_flags = int(row.penalty_flags or 0)
        badge = "🌱 Beginner"
        if golden_stars > 0 and penalty_flags == 0:
            badge = "⭐ Golden Star"
        elif penalty_flags > 0:
            badge = "🚫 Penalty"
        ranked.append(
            {
                "rank": index,
                "student_name": row.student_name,
                "department": row.department or "N/A",
                "total_tasks": total_tasks,
                "golden_star": golden_stars > 0,
                "penalty": penalty_flags > 0,
                "golden_stars": golden_stars,
                "penalty_flags": penalty_flags,
                "badge": badge,
            }
        )
    return ranked
