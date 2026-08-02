from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.models import EliteSprintBid, PointRule, PointTransaction, Submission, SupportMessage, User
from app.services.points import badge_for_points, leaderboard, monthly_points_query, overall_points_query, record_bonus, record_penalty
from app.utils.auth import role_required


students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.route("/")
@role_required("admin")
def index():
    students = User.query.filter_by(role="student").order_by(User.name.asc()).all()
    pending_students = User.query.filter_by(role="student", approval_status="pending").order_by(User.created_at.desc()).all()
    overall = {row.student_id: int(row.overall_points or 0) for row in overall_points_query().all()}
    monthly = {row.student_id: int(row.monthly_points or 0) for row in monthly_points_query().all()}
    ranked = {row["name"]: row for row in leaderboard(limit=100000)}
    badges = {student.id: badge_for_points(overall.get(student.id, 0)) for student in students}
    return render_template(
        "students/index.html",
        students=students,
        pending_students=pending_students,
        overall=overall,
        monthly=monthly,
        ranked=ranked,
        badges=badges,
    )


@students_bp.route("/pending")
@role_required("admin")
def pending_requests():
    students = User.query.filter_by(role="student", approval_status="pending").order_by(User.created_at.desc()).all()
    return render_template("students/pending.html", students=students)


@students_bp.route("/<int:student_id>/approval", methods=["POST"])
@role_required("admin")
def update_approval(student_id):
    student = User.query.filter_by(id=student_id, role="student").first_or_404()
    new_status = request.form.get("approval_status", "").strip().lower()
    if new_status not in {"approved", "rejected"}:
        flash("Choose a valid approval action.", "warning")
        return redirect(url_for("students.index"))

    student.approval_status = new_status
    db.session.commit()
    flash(f"Student request marked as {new_status}.", "success")
    return redirect(url_for("students.index"))


@students_bp.route("/<int:student_id>")
@role_required("admin")
def detail(student_id):
    student = User.query.filter_by(id=student_id, role="student").first_or_404()
    overall = {row.student_id: int(row.overall_points or 0) for row in overall_points_query().all()}
    monthly = {row.student_id: int(row.monthly_points or 0) for row in monthly_points_query().all()}
    submissions = Submission.query.filter_by(student_id=student.id).order_by(Submission.submitted_at.desc()).all()
    transactions = PointTransaction.query.filter_by(student_id=student.id).order_by(PointTransaction.created_at.desc()).all()
    bonus_rules = PointRule.query.filter_by(stream="bonus").order_by(PointRule.id.asc()).all()
    penalty_rules = PointRule.query.filter_by(stream="penalty").order_by(PointRule.id.asc()).all()
    overall_points = overall.get(student.id, 0)
    return render_template(
        "students/detail.html",
        student=student,
        overall=overall_points,
        monthly=monthly.get(student.id, 0),
        badge=badge_for_points(overall_points),
        submissions=submissions,
        transactions=transactions,
        bonus_rules=bonus_rules,
        penalty_rules=penalty_rules,
    )


@students_bp.route("/<int:student_id>/bonus", methods=["POST"])
@role_required("admin")
def bonus(student_id):
    student = User.query.filter_by(id=student_id, role="student").first_or_404()
    try:
        rule = PointRule.query.filter_by(code=request.form.get("rule_code", ""), stream="bonus").first()
        if not rule:
            raise ValueError("Choose a valid bonus reason.")
        points = abs(int(rule.points))
        extra_reason = request.form.get("reason_detail", "").strip()
        reason = f"{rule.title}: {extra_reason}" if extra_reason else rule.title
        if points <= 0:
            raise ValueError("Bonus points must be a positive number.")
        if not reason:
            raise ValueError("Bonus reason is required.")

        record_bonus(student_id=student.id, points=points, reason=reason, approved_by=current_user.id)
        db.session.commit()
        flash("Bonus points awarded successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("students.detail", student_id=student.id))


@students_bp.route("/<int:student_id>/penalty", methods=["POST"])
@role_required("admin")
def penalty(student_id):
    student = User.query.filter_by(id=student_id, role="student").first_or_404()
    try:
        rule = PointRule.query.filter_by(code=request.form.get("rule_code", ""), stream="penalty").first()
        if not rule:
            raise ValueError("Choose a valid penalty reason.")
        points = abs(int(rule.points))
        extra_reason = request.form.get("reason_detail", "").strip()
        reason = f"{rule.title}: {extra_reason}" if extra_reason else rule.title
        if points <= 0:
            raise ValueError("Penalty points must be entered as a positive number.")
        if not reason:
            raise ValueError("Penalty reason is required.")

        record_penalty(student_id=student.id, points=points, reason=reason, approved_by=current_user.id)
        db.session.commit()
        flash("Penalty deducted successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("students.detail", student_id=student.id))


@students_bp.route("/<int:student_id>/delete", methods=["POST"])
@role_required("admin")
def delete(student_id):
    student = User.query.filter_by(id=student_id, role="student").first_or_404()
    try:
        Submission.query.filter_by(student_id=student.id).delete(synchronize_session=False)
        PointTransaction.query.filter_by(student_id=student.id).delete(synchronize_session=False)
        SupportMessage.query.filter_by(student_id=student.id).delete(synchronize_session=False)
        EliteSprintBid.query.filter_by(student_id=student.id).delete(synchronize_session=False)
        db.session.delete(student)
        db.session.commit()
        flash("Student removed successfully.", "success")
        return redirect(url_for("students.index"))
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("students.detail", student_id=student.id))
