from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.models import Submission, Task
from app.services.points import record_award
from app.services.submissions import can_submit_task_on_date, current_submission_date
from app.utils.auth import role_required
from app.utils.uploads import save_uploaded_proof_files


submissions_bp = Blueprint("submissions", __name__, url_prefix="/submissions")


@submissions_bp.route("/task/<int:task_id>/submit", methods=["GET", "POST"])
@role_required("student")
def submit(task_id):
    task = Task.query.get_or_404(task_id)
    today = current_submission_date()
    existing_today = Submission.query.filter_by(task_id=task.id, student_id=current_user.id, submission_date=today).order_by(Submission.submitted_at.desc()).first()
    if request.method == "POST":
        try:
            allowed, message = can_submit_task_on_date(current_user.id, task.id, today)
            if not allowed:
                raise ValueError(message or "You cannot submit this task again today.")

            submission = Submission(task_id=task.id, student_id=current_user.id, submission_date=today)
            submission.description = request.form.get("description", "").strip()
            submission.github_link = request.form.get("github_link", "").strip()
            submission.drive_link = request.form.get("drive_link", "").strip()
            submitted_files = request.files.getlist("proof_files")
            if not submitted_files:
                raise ValueError("Please upload at least one proof file.")
            submission.proof_url = save_uploaded_proof_files(submitted_files, limit=10)
            submission.status = "waiting_approval"
            submission.submitted_at = datetime.utcnow()

            if not submission.description:
                raise ValueError("Proof description is required.")

            db.session.add(submission)
            db.session.commit()
            flash("Submission saved and sent for approval.", "success")
            return redirect(url_for("tasks.detail", task_id=task.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("submissions/form.html", task=task, submission=existing_today, already_submitted_today=existing_today is not None and existing_today.status in ["waiting_approval", "approved", "pending"])


@submissions_bp.route("/pending")
@role_required("admin")
def pending():
    submissions = (
        Submission.query.filter_by(status="waiting_approval")
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    grouped = {}
    for submission in submissions:
        if submission.student_id not in grouped:
            grouped[submission.student_id] = {"student": submission.student, "submissions": []}
        grouped[submission.student_id]["submissions"].append(submission)
    return render_template("submissions/pending.html", grouped_submissions=grouped)


@submissions_bp.route("/status")
@role_required("student")
def status():
    submissions = (
        Submission.query.filter_by(student_id=current_user.id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    return render_template("submissions/status.html", submissions=submissions)


@submissions_bp.route("/<int:submission_id>/approve", methods=["POST"])
@role_required("admin")
def approve(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    try:
        if submission.status == "approved":
            raise ValueError("Submission is already approved.")

        submission.status = "approved"
        submission.admin_remarks = request.form.get("remarks", "").strip()
        submission.reviewed_at = datetime.utcnow()
        submission.reviewed_by = current_user.id
        record_award(
            student_id=submission.student_id,
            task_id=submission.task_id,
            points=submission.task.reward_points,
            reason=f"Approved task: {submission.task.title}",
            approved_by=current_user.id,
        )
        db.session.commit()
        flash("Submission approved and points awarded.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("submissions.pending"))


@submissions_bp.route("/<int:submission_id>/reject", methods=["POST"])
@role_required("admin")
def reject(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    try:
        submission.status = "rejected"
        submission.admin_remarks = request.form.get("remarks", "").strip()
        submission.reviewed_at = datetime.utcnow()
        submission.reviewed_by = current_user.id
        db.session.commit()
        flash("Submission rejected.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("submissions.pending"))
