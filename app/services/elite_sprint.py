import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func

from app import db
from app.models import (
    EliteSprintBid,
    EliteSprintSession,
    PointTransaction,
    SprintVerificationResult,
    Submission,
    Task,
    User,
)


APP_TIMEZONE = os.getenv("ELITE_TIMEZONE", "Asia/Kolkata")
COMPLETION_WINDOW_HOURS = 15


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
    active = EliteSprintSession.query.filter(EliteSprintSession.status == "active").all()
    closed_any = False
    for session in active:
        end = session.bidding_end or session.end_time
        if end and now >= end:
            session.status = "closed"
            session.start_completion_window()
            closed_any = True
    if closed_any:
        db.session.commit()
    try:
        check_and_run_automatic_verification()
    except Exception:
        db.session.rollback()
    return closed_any


def get_active_session():
    close_expired_sprints()
    now = utc_now()
    candidates = (
        EliteSprintSession.query.filter(EliteSprintSession.status == "active")
        .order_by(EliteSprintSession.created_at.desc())
        .all()
    )
    for session in candidates:
        start = session.bidding_starts_at or session.start_time
        end = session.bidding_ends_at or session.end_time
        if start and end and start <= now < end:
            return session
    return None


def get_bidding_window_end(session):
    if not session:
        return None
    return session.bidding_ends_at or session.end_time


def get_completion_window_end(session):
    if not session:
        return None
    return session.completion_ends_at


def get_submission_sprint_session(student_id):
    now = utc_now()
    bids = (
        EliteSprintBid.query.filter_by(student_id=student_id, is_locked=True)
        .order_by(EliteSprintBid.submitted_at.desc())
        .all()
    )
    for bid in bids:
        session = bid.session
        if not session or session.verified:
            continue
        bidding_end = session.bidding_end or session.end_time
        if not bidding_end:
            continue
        completion_deadline = session.completion_ends_at or (
            bidding_end + timedelta(hours=COMPLETION_WINDOW_HOURS)
        )
        if now < completion_deadline:
            return session
    return None


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
        bid = row.EliteSprintBid
        leaderboard.append(
            {
                "rank": index,
                "student_name": row.student_name,
                "department": row.department or "Not set",
                "total_tasks": total,
                "badge": participation_badge(index, total),
                "bid": bid,
                "golden_star": bid.has_golden_star if bid else False,
                "penalty": bid.student.has_active_sprint_penalty if bid and bid.student else False,
                "golden_stars": (bid.student.golden_stars or 0) if bid and bid.student else 0,
                "penalty_flags": (bid.student.penalty_flags or 0) if bid and bid.student else 0,
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


def task_identifier(task):
    if not task:
        return None
    if task.task_code:
        return task.task_code.strip().upper()
    return str(task.id)


def verification_for_student(session_id, student_id):
    return SprintVerificationResult.query.filter_by(
        session_id=session_id, student_id=student_id
    ).first()


def get_sprint_verification_results(session_id):
    return (
        SprintVerificationResult.query.filter_by(session_id=session_id)
        .order_by(SprintVerificationResult.student_id.asc())
        .all()
    )


def run_sprint_verification(session_id, mode="automatic"):
    session = EliteSprintSession.query.get(session_id)
    if not session:
        raise ValueError("Sprint session not found.")
    if session.verified:
        return {"already_verified": True, "golden_star": [], "penalty_count": 0, "results_created": 0}

    bids = EliteSprintBid.query.filter_by(session_id=session.id).all()

    golden_star_students = []
    penalty_count = 0
    results_created = 0

    for bid in bids:
        student = bid.student
        if student is None:
            continue

        existing = SprintVerificationResult.query.filter_by(
            session_id=session.id, student_id=student.id
        ).first()
        if existing:
            if existing.is_golden_star:
                golden_star_students.append(student.name)
            if existing.has_penalty:
                penalty_count += 1
            continue

        # Use identifiers for comparison (Task Code or ID)
        planned_identifiers = set()
        identifier_to_task = {}
        for ptid in bid.planned_task_ids:
            task = Task.query.filter((Task.id == ptid) | (Task.task_code == ptid)).first()
            if task:
                tid = task_identifier(task)
                planned_identifiers.add(tid)
                identifier_to_task[tid] = task

        if not planned_identifiers:
            continue

        # Get all submissions for this sprint session (ignore approval status)
        submitted_identifiers = set()
        subs = Submission.query.filter_by(
            student_id=student.id, sprint_session_id=session.id
        ).all()
        for sub in subs:
            tid = task_identifier(sub.task)
            if tid:
                submitted_identifiers.add(tid)

        # Compare current sprint session data only (extra submissions allowed)
        missing_identifiers = planned_identifiers - submitted_identifiers
        penalty_points = 0

        if not missing_identifiers:
            # All bidded tasks submitted
            student.golden_stars = (student.golden_stars or 0) + 1
            bid.has_golden_star = True
            golden_star_students.append(student.name)
            result = SprintVerificationResult(
                session_id=session.id,
                student_id=student.id,
                planned_task_ids=",".join(sorted(planned_identifiers)),
                submitted_task_ids=",".join(sorted(submitted_identifiers)),
                missing_task_ids="",
                penalty_points=0,
                earned_golden_star=True,
            )
        else:
            # Penalty for missing bidded tasks
            for tid in sorted(missing_identifiers):
                task = identifier_to_task.get(tid)
                if task:
                    penalty = PointTransaction.penalty(
                        student_id=student.id,
                        points=task.reward_points,
                        reason=f"Sprint incomplete: {task.task_code or task.id}",
                        approved_by=None,
                    )
                    db.session.add(penalty)
                    penalty_points += task.reward_points
            student.penalty_flags = (student.penalty_flags or 0) + 1
            student.has_active_sprint_penalty = True
            penalty_count += 1
            result = SprintVerificationResult(
                session_id=session.id,
                student_id=student.id,
                planned_task_ids=",".join(sorted(planned_identifiers)),
                submitted_task_ids=",".join(sorted(submitted_identifiers)),
                missing_task_ids=",".join(sorted(missing_identifiers)),
                penalty_points=penalty_points,
                earned_golden_star=False,
            )
        db.session.add(result)
        results_created += 1

    session.mark_verified(mode=mode)
    db.session.commit()
    return {
        "already_verified": False,
        "golden_star": golden_star_students,
        "penalty_count": penalty_count,
        "results_created": results_created,
    }


def check_and_run_automatic_verification():
    now = utc_now()
    sessions = EliteSprintSession.query.filter(
        EliteSprintSession.verified.is_(False),
        EliteSprintSession.completion_ends_at.isnot(None),
        EliteSprintSession.completion_ends_at <= now,
    ).all()
    for session in sessions:
        if session.verified:
            continue
        try:
            run_sprint_verification(session.id, mode="automatic")
        except Exception:
            db.session.rollback()
    return len(sessions)
