from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.models import PointTransaction, Submission, Task
from app.services.submissions import submitted_task_ids_for_date
from app.utils.auth import role_required
from app.utils.uploads import save_uploaded_file


tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M")


@tasks_bp.route("/")
@role_required("admin", "student")
def index():
    tasks = Task.query.order_by(Task.created_at.asc()).all()
    submitted_today_ids = submitted_task_ids_for_date(current_user.id) if current_user.role == "student" else set()
    return render_template("tasks/index.html", tasks=tasks, submitted_today_ids=submitted_today_ids)


@tasks_bp.route("/daily")
@role_required("admin", "student")
def daily():
    tasks = Task.query.filter_by(task_type="daily").order_by(Task.created_at.asc()).all()
    submitted_today_ids = submitted_task_ids_for_date(current_user.id) if current_user.role == "student" else set()
    return render_template("tasks/index.html", tasks=tasks, title="Daily Tasks", submitted_today_ids=submitted_today_ids)


@tasks_bp.route("/weekly")
@role_required("admin", "student")
def weekly():
    tasks = Task.query.filter_by(task_type="weekly").order_by(Task.created_at.asc()).all()
    submitted_today_ids = submitted_task_ids_for_date(current_user.id) if current_user.role == "student" else set()
    return render_template("tasks/index.html", tasks=tasks, title="Weekly Tasks", submitted_today_ids=submitted_today_ids)


@tasks_bp.route("/monthly")
@role_required("admin", "student")
def monthly():
    tasks = Task.query.filter_by(task_type="monthly").order_by(Task.created_at.asc()).all()
    submitted_today_ids = submitted_task_ids_for_date(current_user.id) if current_user.role == "student" else set()
    return render_template("tasks/index.html", tasks=tasks, title="Monthly Tasks", submitted_today_ids=submitted_today_ids)


@tasks_bp.route("/create", methods=["GET", "POST"])
@role_required("admin")
def create():
    if request.method == "POST":
        try:
            task = Task(
                title=request.form.get("title", "").strip(),
                category=request.form.get("category", "").strip() or "General",
                description=request.form.get("description", "").strip(),
                instructions=request.form.get("instructions", "").strip(),
                reference_links=request.form.get("reference_links", "").strip(),
                reward_points=int(request.form.get("reward_points", 0)),
                task_type=request.form.get("task_type", "daily"),
                status=request.form.get("status", "active"),
                start_at=parse_date(request.form.get("start_at")),
                due_at=parse_date(request.form.get("due_at")),
                deadline_at=parse_date(request.form.get("deadline_at")),
                created_by=current_user.id,
            )
            if not task.title:
                raise ValueError("Task title is required.")
            if task.reward_points < 0:
                raise ValueError("Reward points cannot be negative.")

            task.attachment_path = save_uploaded_file(request.files.get("attachment"), "tasks")
            db.session.add(task)
            db.session.commit()
            flash("Task created successfully.", "success")
            return redirect(url_for("tasks.index"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("tasks/form.html")


@tasks_bp.route("/<int:task_id>")
@role_required("admin", "student")
def detail(task_id):
    task = Task.query.get_or_404(task_id)
    submitted_today = False
    if current_user.role == "student":
        submitted_today = task.id in submitted_task_ids_for_date(current_user.id)
    return render_template("tasks/detail.html", task=task, submitted_today=submitted_today)


@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == "POST":
        try:
            task.title = request.form.get("title", "").strip()
            task.category = request.form.get("category", "").strip() or "General"
            task.description = request.form.get("description", "").strip()
            task.instructions = request.form.get("instructions", "").strip()
            task.reference_links = request.form.get("reference_links", "").strip()
            task.reward_points = int(request.form.get("reward_points", 0) or 0)
            task.task_type = request.form.get("task_type", task.task_type)
            task.status = request.form.get("status", task.status)
            task.start_at = parse_date(request.form.get("start_at")) or task.start_at
            task.due_at = parse_date(request.form.get("due_at")) or task.due_at
            task.deadline_at = parse_date(request.form.get("deadline_at")) or task.deadline_at
            if not task.title:
                raise ValueError("Task title is required.")
            if task.reward_points < 0:
                raise ValueError("Reward points cannot be negative.")

            uploaded_file = request.files.get("attachment")
            if uploaded_file and uploaded_file.filename:
                from app.utils.uploads import save_uploaded_file
                task.attachment_path = save_uploaded_file(uploaded_file, "tasks")

            db.session.commit()
            flash("Task updated successfully.", "success")
            return redirect(url_for("tasks.detail", task_id=task.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("tasks/form.html", task=task, editing=True)


@tasks_bp.route("/<int:task_id>/delete", methods=["POST"])
@role_required("admin")
def delete(task_id):
    task = Task.query.get_or_404(task_id)
    try:
        Submission.query.filter_by(task_id=task.id).delete(synchronize_session=False)
        PointTransaction.query.filter_by(task_id=task.id).delete(synchronize_session=False)
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("tasks.index"))
