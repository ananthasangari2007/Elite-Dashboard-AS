import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField, TimeField
from wtforms.validators import DataRequired, ValidationError

from app import db
from app.models import (
    EliteSprintBid,
    EliteSprintBidTask,
    EliteSprintSession,
    SprintVerificationResult,
    Task,
    User,
)
from app.services.elite_sprint import (
    VERIFICATION_WINDOW_HOURS,
    create_sprint,
    get_sprint_for_date,
    get_today_sprint,
    get_sprint_leaderboard,
    process_expired_sprint_verifications,
)

elite_sprint_bp = Blueprint(
    "elite_sprint",
    __name__,
    url_prefix="/elite-sprint",
)

APP_TIMEZONE = os.getenv("ELITE_TIMEZONE", "Asia/Kolkata")


def sprint_timezone():
    try:
        return ZoneInfo(APP_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def validate_sprint_date(form, field):
    sprint_date = field.data
    if sprint_date < utc_now().date():
        raise ValidationError("Cannot create a sprint for a past date.")
    existing = get_sprint_for_date(sprint_date)
    if existing:
        raise ValidationError("A sprint already exists for this date.")


class SprintCreateForm(FlaskForm):
    sprint_date = DateField("Sprint Date", validators=[DataRequired(), validate_sprint_date])
    start_time = TimeField("Start Time", validators=[DataRequired()])
    end_time = TimeField("End Time", validators=[DataRequired()])
    submit = SubmitField("Create Sprint")


class SprintBidForm(FlaskForm):
    daily_tasks = None
    weekly_tasks = None
    monthly_tasks = None
    submit = SubmitField("Save Sprint")


@elite_sprint_bp.route("/admin")
@login_required
def admin():
    process_expired_sprint_verifications()
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard.home"))

    today = utc_now().date()
    today_sprint = get_sprint_for_date(today)
    form = SprintCreateForm()
    sprint_stats = {"locked_students": 0, "verified_students": 0}
    if today_sprint:
        locked = EliteSprintBid.query.filter_by(session_id=today_sprint.id, is_locked=True).count()
        verified = EliteSprintBid.query.filter_by(session_id=today_sprint.id, is_verified=True).count()
        sprint_stats = {"locked_students": locked, "verified_students": verified}

    return render_template(
        "elite_sprint/admin.html",
        form=form,
        today_sprint=today_sprint,
        current_time=datetime.utcnow(),
        sprint_stats=sprint_stats,
        timezone_label=APP_TIMEZONE,
    )


@elite_sprint_bp.route("/admin", methods=["POST"])
@login_required
def admin_create_sprint():
    process_expired_sprint_verifications()
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard.home"))

    form = SprintCreateForm()
    if form.validate_on_submit():
        sprint_date = form.sprint_date.data
        start_time = form.start_time.data
        end_time = form.end_time.data

        if isinstance(start_time, datetime):
            start_time = start_time.time()
        if isinstance(end_time, datetime):
            end_time = end_time.time()

        if end_time <= start_time:
            flash("End time must be after start time.", "error")
            today_sprint = get_sprint_for_date(sprint_date)
            return render_template(
                "elite_sprint/admin.html",
                form=form,
                today_sprint=today_sprint,
                current_time=datetime.utcnow(),
                sprint_stats={"locked_students": 0, "verified_students": 0},
                timezone_label=APP_TIMEZONE,
            )

        session, error = create_sprint(sprint_date, start_time, end_time)
        if error:
            flash(error, "error")
        else:
            flash(f"Sprint created for {sprint_date.strftime('%d %b %Y')}.", "success")
        return redirect(url_for("elite_sprint.admin"))

    flash("Please fix the errors below.", "error")
    today = utc_now().date()
    today_sprint = get_sprint_for_date(today)
    return render_template(
        "elite_sprint/admin.html",
        form=form,
        today_sprint=today_sprint,
        current_time=datetime.utcnow(),
        sprint_stats={"locked_students": 0, "verified_students": 0},
        timezone_label=APP_TIMEZONE,
    )


@elite_sprint_bp.route("/student")
@login_required
def student():
    process_expired_sprint_verifications()
    if current_user.role != "student":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard.home"))

    today_sprint = get_today_sprint()
    if not today_sprint:
        return render_template(
            "elite_sprint/student.html",
            sprint_open=False,
            message="Sprint bidding is currently closed.",
            current_time=datetime.utcnow(),
        )

    bid = EliteSprintBid.query.filter_by(
        session_id=today_sprint.id,
        student_id=current_user.id,
    ).first()

    if bid and bid.is_locked:
        return render_template(
            "elite_sprint/student.html",
            sprint_open=False,
            bid=bid,
            today_sprint=today_sprint,
            message="Sprint locked until the next sprint session.",
            current_time=datetime.utcnow(),
        )

    return render_template(
        "elite_sprint/student.html",
        sprint_open=True,
        today_sprint=today_sprint,
        bid=bid,
        current_time=datetime.utcnow(),
    )


@elite_sprint_bp.route("/student", methods=["POST"])
@login_required
def student_submit():
    process_expired_sprint_verifications()
    if current_user.role != "student":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard.home"))

    today_sprint = get_today_sprint()
    if not today_sprint:
        flash("Sprint bidding is currently closed.", "error")
        return redirect(url_for("elite_sprint.student"))

    existing_bid = EliteSprintBid.query.filter_by(
        session_id=today_sprint.id,
        student_id=current_user.id,
    ).first()

    if existing_bid and existing_bid.is_locked:
        flash("Sprint locked until the next sprint session.", "error")
        return redirect(url_for("elite_sprint.student"))

    daily_task_ids_raw = request.form.getlist("daily_tasks")
    weekly_task_ids_raw = request.form.getlist("weekly_tasks")
    monthly_task_ids_raw = request.form.getlist("monthly_tasks")

    daily_task_ids = [t.strip() for t in daily_task_ids_raw if t.strip()]
    weekly_task_ids = [t.strip() for t in weekly_task_ids_raw if t.strip()]
    monthly_task_ids = [t.strip() for t in monthly_task_ids_raw if t.strip()]

    all_task_ids = daily_task_ids + weekly_task_ids + monthly_task_ids

    if len(daily_task_ids) < 2:
        flash("Daily category requires at least 2 task IDs.", "error")
        return redirect(url_for("elite_sprint.student"))
    if len(weekly_task_ids) < 2:
        flash("Weekly category requires at least 2 task IDs.", "error")
        return redirect(url_for("elite_sprint.student"))
    if len(monthly_task_ids) < 2:
        flash("Monthly category requires at least 2 task IDs.", "error")
        return redirect(url_for("elite_sprint.student"))

    if not all_task_ids:
        flash("At least one task ID is required.", "error")
        return redirect(url_for("elite_sprint.student"))

    seen = set()
    for tid in all_task_ids:
        if tid in seen:
            flash(f"Duplicate task ID found: {tid}. Each task ID must be unique.", "error")
            return redirect(url_for("elite_sprint.student"))
        seen.add(tid)

    resolved_task_ids = []
    for tid in all_task_ids:
        task = Task.query.filter(
            (Task.id == tid) | (Task.task_code == tid)
        ).first()
        if not task:
            flash(f"Task ID '{tid}' does not exist in the task catalog.", "error")
            return redirect(url_for("elite_sprint.student"))
        resolved_task_ids.append(task.id)

    if existing_bid:
        existing_bid.tasks.clear()
        for task_id in resolved_task_ids:
            category = "daily"
            if task_id in [t.id for t in Task.query.filter(Task.id.in_(weekly_task_ids)).all()]:
                category = "weekly"
            elif task_id in [t.id for t in Task.query.filter(Task.id.in_(monthly_task_ids)).all()]:
                category = "monthly"
            bid_task = EliteSprintBidTask(bid=existing_bid, task_id=task_id, category=category)
            db.session.add(bid_task)
        existing_bid.is_locked = True
        existing_bid.locked_at = datetime.utcnow()
        existing_bid.verification_due_at = existing_bid.locked_at + timedelta(hours=VERIFICATION_WINDOW_HOURS)
    else:
        now = datetime.utcnow()
        bid = EliteSprintBid(
            session_id=today_sprint.id,
            student_id=current_user.id,
            is_locked=True,
            locked_at=now,
            verification_due_at=now + timedelta(hours=VERIFICATION_WINDOW_HOURS),
        )
        db.session.add(bid)
        db.session.flush()
        for task_id in resolved_task_ids:
            category = "daily"
            if task_id in [t.id for t in Task.query.filter(Task.id.in_(weekly_task_ids)).all()]:
                category = "weekly"
            elif task_id in [t.id for t in Task.query.filter(Task.id.in_(monthly_task_ids)).all()]:
                category = "monthly"
            bid_task = EliteSprintBidTask(bid=bid, task_id=task_id, category=category)
            db.session.add(bid_task)

    db.session.commit()
    flash("Sprint locked until the next sprint session.", "success")
    return redirect(url_for("elite_sprint.student"))


@elite_sprint_bp.route("/leaderboard")
@login_required
def leaderboard():
    process_expired_sprint_verifications()
    rows = get_sprint_leaderboard()
    return render_template(
        "elite_sprint/leaderboard.html",
        leaderboard=rows,
        timezone_label=APP_TIMEZONE,
    )


@elite_sprint_bp.route("/verify")
@login_required
def verify():
    process_expired_sprint_verifications()
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard.home"))

    session_id = request.args.get("session_id", type=int)
    if session_id:
        session_obj = EliteSprintSession.query.get_or_404(session_id)
    else:
        session_obj = (
            EliteSprintSession.query.order_by(EliteSprintSession.sprint_date.desc())
            .first()
        )

    results = []
    if session_obj:
        results = (
            SprintVerificationResult.query.filter_by(session_id=session_obj.id)
            .order_by(SprintVerificationResult.verified_at.desc())
            .all()
        )

    return render_template(
        "elite_sprint/verification_results.html",
        session=session_obj,
        results=results,
        timezone_label=APP_TIMEZONE,
    )
