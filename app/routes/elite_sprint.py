import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, DateTimeField, SubmitField
from wtforms.validators import DataRequired

elite_sprint_bp = Blueprint(
    "elite_sprint",
    __name__,
    url_prefix="/elite-sprint"
)

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


def ensure_active_session():
    active = get_active_session()
    if active:
        return active
    now = utc_now()
    sprint_date = now.date()
    bidding_start = now
    bidding_end = now + timedelta(days=7)
    session = EliteSprintSession(
        sprint_date=sprint_date,
        sprint_type="overall",
        start_time=bidding_start,
        end_time=bidding_end,
        bidding_starts_at=bidding_start,
        bidding_ends_at=bidding_end,
        status="active",
        created_by=0,
    )
    db.session.add(session)
    db.session.commit()
    return session


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


class SprintSessionForm(FlaskForm):
    sprint_type = SelectField(
        "Sprint Type",
        choices=[("overall", "Overall"), ("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")],
        validators=[DataRequired()],
    )
    sprint_date = DateField("Sprint Date", validators=[DataRequired()])
    start_time = DateTimeField("Start Time", validators=[DataRequired()])
    end_time = DateTimeField("End Time", validators=[DataRequired()])
    submit = SubmitField("Open Sprint")


@elite_sprint_bp.route("/")
@login_required
def index():
    try:
        ensure_active_session()
    except Exception:
        pass
    try:
        latest = latest_session()
    except Exception:
        latest = None
    try:
        active = get_active_session()
    except Exception:
        active = None
    if current_user.role == "admin":
        form = SprintSessionForm()
        try:
            metrics = sprint_metrics(latest) if latest else {
                "participants": 0,
                "daily": 0,
                "weekly": 0,
                "monthly": 0,
                "highest_bidder": "No bids yet",
                "participation": 0,
            }
        except Exception:
            metrics = {
                "participants": 0,
                "daily": 0,
                "weekly": 0,
                "monthly": 0,
                "highest_bidder": "No bids yet",
                "participation": 0,
            }
        return render_template(
            "elite_sprint/admin.html",
            form=form,
            timezone_label=APP_TIMEZONE,
            active_session=active,
            latest_session=latest,
            metrics=metrics,
        )
    elif current_user.role == "student":
        bid = None
        verification_result = None
        visible_sections = {"daily", "weekly", "monthly"}
        completion_end_local = None
        if latest:
            try:
                bid = (
                    EliteSprintBid.query.filter_by(session_id=latest.id, student_id=current_user.id)
                    .order_by(EliteSprintBid.submitted_at.desc())
                    .first()
                )
                verification_result = SprintVerificationResult.query.filter_by(
                    session_id=latest.id, student_id=current_user.id
                ).first()
            except Exception:
                bid = None
                verification_result = None
            if latest.completion_ends_at:
                try:
                    completion_end_local = utc_datetime_to_local(latest.completion_ends_at)
                except Exception:
                    completion_end_local = None
        return render_template(
            "elite_sprint/student.html",
            latest_session=latest,
            active_session=active,
            bid=bid,
            verification_result=verification_result,
            visible_sections=visible_sections,
            completion_end_local=completion_end_local,
        )
    try:
        board = sprint_leaderboard(latest.id if latest else None, limit=10)
    except Exception:
        board = []
    return render_template("elite_sprint/leaderboard.html", leaderboard=board)


@elite_sprint_bp.route("/", methods=["POST"])
@login_required
def handle_form():
    if current_user.role == "admin":
        session_id = request.form.get("session_id")
        if session_id:
            try:
                result = run_sprint_verification(int(session_id), mode="manual")
                flash(f"Verification complete: {result['results_created']} result(s) created.", "success")
            except Exception as e:
                flash(f"Verification failed: {e}", "error")
            return redirect(url_for("elite_sprint.index"))
        form = SprintSessionForm()
        if form.validate_on_submit():
            try:
                sprint_date = form.sprint_date.data
                start_time = local_datetime_to_utc(form.start_time.data)
                end_time = local_datetime_to_utc(form.end_time.data)
                session = EliteSprintSession(
                    sprint_date=sprint_date,
                    sprint_type=form.sprint_type.data,
                    start_time=start_time,
                    end_time=end_time,
                    bidding_starts_at=start_time,
                    bidding_ends_at=end_time,
                    created_by=current_user.id,
                )
                db.session.add(session)
                db.session.commit()
                flash("Sprint session opened successfully.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Failed to open sprint: {e}", "error")
            return redirect(url_for("elite_sprint.index"))
        try:
            metrics = sprint_metrics(latest_session()) if latest_session() else {
                "participants": 0,
                "daily": 0,
                "weekly": 0,
                "monthly": 0,
                "highest_bidder": "No bids yet",
                "participation": 0,
            }
        except Exception:
            metrics = {
                "participants": 0,
                "daily": 0,
                "weekly": 0,
                "monthly": 0,
                "highest_bidder": "No bids yet",
                "participation": 0,
            }
        try:
            active = get_active_session()
        except Exception:
            active = None
        try:
            latest = latest_session()
        except Exception:
            latest = None
        return render_template(
            "elite_sprint/admin.html",
            form=form,
            timezone_label=APP_TIMEZONE,
            active_session=active,
            latest_session=latest,
            metrics=metrics,
        )
    elif current_user.role == "student":
        try:
            latest = latest_session()
        except Exception:
            latest = None
        if not latest:
            flash("No active sprint session.", "error")
            return redirect(url_for("elite_sprint.index"))
        daily_count = request.form.get("daily_count", 0, type=int)
        weekly_count = request.form.get("weekly_count", 0, type=int)
        monthly_count = request.form.get("monthly_count", 0, type=int)
        daily_tasks = [t.strip().upper() for t in request.form.getlist("daily_tasks") if t.strip()]
        weekly_tasks = [t.strip().upper() for t in request.form.getlist("weekly_tasks") if t.strip()]
        monthly_tasks = [t.strip().upper() for t in request.form.getlist("monthly_tasks") if t.strip()]
        try:
            existing_bid = EliteSprintBid.query.filter_by(session_id=latest.id, student_id=current_user.id).first()
            task_ids = daily_tasks + weekly_tasks + monthly_tasks
            if existing_bid:
                existing_bid.daily_count = daily_count
                existing_bid.weekly_count = weekly_count
                existing_bid.monthly_count = monthly_count
                existing_bid.daily_tasks = daily_tasks
                existing_bid.weekly_tasks = weekly_tasks
                existing_bid.monthly_tasks = monthly_tasks
                existing_bid.task_ids = task_ids
            else:
                bid = EliteSprintBid(
                    session_id=latest.id,
                    student_id=current_user.id,
                    daily_count=daily_count,
                    weekly_count=weekly_count,
                    monthly_count=monthly_count,
                    daily_tasks=daily_tasks,
                    weekly_tasks=weekly_tasks,
                    monthly_tasks=monthly_tasks,
                    task_ids=task_ids,
                )
                db.session.add(bid)
            db.session.commit()
            flash("Sprint bid saved successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to save bid: {e}", "error")
        return redirect(url_for("elite_sprint.index"))
    return redirect(url_for("elite_sprint.index"))


@elite_sprint_bp.route("/analytics")
@login_required
def analytics():
    try:
        latest = latest_session()
    except Exception:
        latest = None
    if not latest:
        metrics = {
            "participants": 0,
            "average_tasks": 0,
            "highest_daily": 0,
            "highest_weekly": 0,
            "highest_monthly": 0,
            "trend_labels": [],
            "trend_values": [],
        }
        return render_template("elite_sprint/analytics.html", metrics=metrics)
    try:
        total_bids = EliteSprintBid.query.filter_by(session_id=latest.id).count()
        students = User.query.filter_by(role="student").count()
        participants = total_bids
        avg_tasks = 0
        highest_daily = 0
        highest_weekly = 0
        highest_monthly = 0
        if total_bids > 0:
            rows = EliteSprintBid.query.filter_by(session_id=latest.id).all()
            all_daily = [b.daily_count or 0 for b in rows]
            all_weekly = [b.weekly_count or 0 for b in rows]
            all_monthly = [b.monthly_count or 0 for b in rows]
            avg_tasks = round((sum(all_daily) + sum(all_weekly) + sum(all_monthly)) / total_bids, 2)
            highest_daily = max(all_daily) if all_daily else 0
            highest_weekly = max(all_weekly) if all_weekly else 0
            highest_monthly = max(all_monthly) if all_monthly else 0
        metrics = {
            "participants": participants,
            "average_tasks": avg_tasks,
            "highest_daily": highest_daily,
            "highest_weekly": highest_weekly,
            "highest_monthly": highest_monthly,
            "trend_labels": [],
            "trend_values": [],
        }
    except Exception:
        metrics = {
            "participants": 0,
            "average_tasks": 0,
            "highest_daily": 0,
            "highest_weekly": 0,
            "highest_monthly": 0,
            "trend_labels": [],
            "trend_values": [],
        }
    return render_template("elite_sprint/analytics.html", metrics=metrics)


@elite_sprint_bp.route("/verification_results/<int:session_id>")
@login_required
def verification_results(session_id):
    try:
        session = EliteSprintSession.query.get_or_404(session_id)
        results = (
            SprintVerificationResult.query.filter_by(session_id=session_id)
            .order_by(SprintVerificationResult.student_id.asc())
            .all()
        )
    except Exception:
        session = None
        results = []
    return render_template(
        "elite_sprint/verification_results.html",
        session=session,
        results=results,
        timezone_label=APP_TIMEZONE,
    )
