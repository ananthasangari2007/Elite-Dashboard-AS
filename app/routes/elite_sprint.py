import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import DateField, SelectField, SubmitField, TimeField
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
    get_sprint_leaderboard,
    get_local_now,
    get_today_sprint,
    process_expired_sprint_verifications,
    run_sprint_verification,
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
    sprint_mode = getattr(form, "sprint_mode", None)
    mode = sprint_mode.data if sprint_mode and sprint_mode.data else "overall"
    existing = EliteSprintSession.query.filter_by(
        sprint_date=sprint_date, sprint_mode=mode
    ).first()
    if existing:
        raise ValidationError(f"A sprint already exists for this date with mode '{mode}'.")


SPRINT_MODE_CHOICES = [
    ("overall", "Overall (All Sections)"),
    ("daily", "Daily Only"),
    ("weekly", "Weekly Only"),
    ("monthly", "Monthly Only"),
]


class SprintCreateForm(FlaskForm):
    sprint_date = DateField("Sprint Date", validators=[DataRequired(), validate_sprint_date])
    sprint_mode = SelectField("Sprint Mode", choices=SPRINT_MODE_CHOICES, default="overall", validators=[DataRequired()])
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

    sprint_leaderboard = []
    submitted_students = []
    pending_students = []
    total_students = User.query.filter_by(role="student").count()

    if today_sprint:
        try:
            sprint_leaderboard = get_sprint_leaderboard(today_sprint.id)

            all_students = User.query.filter_by(role="student").all()
            submitted_students = []
            pending_students = []

            bid_map = {
                bid.student_id: bid
                for bid in EliteSprintBid.query.filter_by(session_id=today_sprint.id).all()
            }

            for student in all_students:
                bid = bid_map.get(student.id)
                if bid and bid.is_locked:
                    total_tasks = sum(1 for _ in bid.tasks)
                    submitted_students.append({
                        "name": student.name,
                        "email": student.email,
                        "submission_time": bid.locked_at,
                        "total_tasks": total_tasks,
                    })
                else:
                    pending_students.append({
                        "name": student.name,
                        "email": student.email,
                    })
        except Exception:
            db.session.rollback()

    return render_template(
        "elite_sprint/admin.html",
        form=form,
        today_sprint=today_sprint,
        sprint_start_time=today_sprint.start_time if today_sprint else None,
        sprint_end_time=today_sprint.end_time if today_sprint else None,
        now_time=get_local_now().time(),
        sprint_leaderboard=sprint_leaderboard,
        submitted_students=submitted_students,
        pending_students=pending_students,
        timezone_label=APP_TIMEZONE,
        total_students=total_students,
    )


@elite_sprint_bp.route("/admin", methods=["POST"])
@login_required
def admin_create_sprint():
    process_expired_sprint_verifications()
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard.home"))

    try:
        sprint_date = datetime.strptime(request.form["sprint_date"], "%Y-%m-%d").date()
        sprint_mode = request.form.get("sprint_mode", "overall")
        start_time = datetime.strptime(request.form["start_time"], "%H:%M").time()
        end_time = datetime.strptime(request.form["end_time"], "%H:%M").time()

        if end_time <= start_time:
            flash("End time must be after start time.", "error")
            return redirect(url_for("elite_sprint.admin"))

        existing = EliteSprintSession.query.filter_by(
            sprint_date=sprint_date,
            is_active=True
        ).first()

        if existing:
            flash("An active sprint already exists for this date.", "warning")
            return redirect(url_for("elite_sprint.admin"))

        session = EliteSprintSession(
            sprint_date=sprint_date,
            start_time=start_time,
            end_time=end_time,
            sprint_mode=sprint_mode,
            is_active=True
        )
        db.session.add(session)
        db.session.commit()

        flash(f"Sprint created for {sprint_date.strftime('%d %b %Y')} ({sprint_mode}).", "success")
        return redirect(url_for("elite_sprint.admin"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("SPRINT CREATE FAILED")
        flash("Unable to create sprint. Check server logs.", "danger")
        return redirect(url_for("elite_sprint.admin"))


@elite_sprint_bp.route("/admin/create", methods=["POST"])
@login_required
def create():
    process_expired_sprint_verifications()
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard.home"))

    try:
        sprint_date = datetime.strptime(request.form["sprint_date"], "%Y-%m-%d").date()
        sprint_mode = request.form.get("sprint_mode", "overall")
        start_time = datetime.strptime(request.form["start_time"], "%H:%M").time()
        end_time = datetime.strptime(request.form["end_time"], "%H:%M").time()

        if end_time <= start_time:
            flash("End time must be after start time.", "error")
            return redirect(url_for("elite_sprint.admin"))

        existing = EliteSprintSession.query.filter_by(
            sprint_date=sprint_date,
            is_active=True
        ).first()

        if existing:
            flash("An active sprint already exists for this date.", "warning")
            return redirect(url_for("elite_sprint.admin"))

        session = EliteSprintSession(
            sprint_date=sprint_date,
            start_time=start_time,
            end_time=end_time,
            sprint_mode=sprint_mode,
            is_active=True
        )
        db.session.add(session)
        db.session.commit()

        flash(f"Sprint created for {sprint_date.strftime('%d %b %Y')} ({sprint_mode}).", "success")
        return redirect(url_for("elite_sprint.admin"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("SPRINT CREATE FAILED")
        flash("Unable to create sprint. Check server logs.", "danger")
        return redirect(url_for("elite_sprint.admin"))


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
            sprint_mode=None,
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
            sprint_mode=today_sprint.sprint_mode,
            message="Sprint locked until the next sprint session.",
        )

    return render_template(
        "elite_sprint/student.html",
        sprint_open=True,
        today_sprint=today_sprint,
        bid=bid,
        sprint_mode=today_sprint.sprint_mode,
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

    sprint_mode = today_sprint.sprint_mode or "overall"

    daily_task_ids_raw = request.form.getlist("daily_tasks")
    weekly_task_ids_raw = request.form.getlist("weekly_tasks")
    monthly_task_ids_raw = request.form.getlist("monthly_tasks")

    daily_task_ids = [t.strip() for t in daily_task_ids_raw if t.strip()]
    weekly_task_ids = [t.strip() for t in weekly_task_ids_raw if t.strip()]
    monthly_task_ids = [t.strip() for t in monthly_task_ids_raw if t.strip()]

    visible_sections = []
    if sprint_mode == "overall":
        visible_sections = ["daily", "weekly", "monthly"]
    elif sprint_mode == "daily":
        visible_sections = ["daily"]
    elif sprint_mode == "weekly":
        visible_sections = ["weekly"]
    elif sprint_mode == "monthly":
        visible_sections = ["monthly"]

    section_map = {
        "daily": daily_task_ids,
        "weekly": weekly_task_ids,
        "monthly": monthly_task_ids,
    }

    for section in visible_sections:
        task_ids = section_map[section]
        if len(task_ids) < 2:
            flash(f"{section.capitalize()} category requires at least 2 task IDs.", "error")
            return redirect(url_for("elite_sprint.student"))

    all_task_ids = daily_task_ids + weekly_task_ids + monthly_task_ids

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
        existing_bid.submitted_at = datetime.utcnow()
        existing_bid.verification_due_at = existing_bid.locked_at + timedelta(hours=VERIFICATION_WINDOW_HOURS)
    else:
        now = datetime.utcnow()
        bid = EliteSprintBid(
            session_id=today_sprint.id,
            student_id=current_user.id,
            is_locked=True,
            locked_at=now,
            submitted_at=now,
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


@elite_sprint_bp.route("/admin/verify-bot", methods=["POST"])
@login_required
def run_verification_bot():
    process_expired_sprint_verifications()
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard.home"))

    session_id = request.form.get("session_id", type=int)
    if session_id:
        session_obj = EliteSprintSession.query.get_or_404(session_id)
    else:
        session_obj = (
            EliteSprintSession.query.order_by(EliteSprintSession.sprint_date.desc())
            .first()
        )

    if not session_obj:
        flash("No sprint session found.", "error")
        return redirect(url_for("elite_sprint.admin"))

    try:
        count = run_sprint_verification(session_obj.id)
        flash(f"Verification completed for {count} locked bid(s).", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Verification failed: {exc}", "error")

    return redirect(url_for("elite_sprint.admin"))
