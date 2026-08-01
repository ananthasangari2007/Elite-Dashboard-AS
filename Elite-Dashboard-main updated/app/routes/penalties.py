from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.models import User
from app.services.points import record_penalty
from app.utils.auth import role_required


penalties_bp = Blueprint("penalties", __name__, url_prefix="/penalties")


@penalties_bp.route("/create", methods=["GET", "POST"])
@role_required("admin")
def create():
    students = User.query.filter_by(role="student").order_by(User.name.asc()).all()
    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id"))
            points = int(request.form.get("points"))
            reason = request.form.get("reason", "").strip()
            if points <= 0:
                raise ValueError("Enter penalty points as a positive number. The system stores it as negative.")
            if not reason:
                raise ValueError("Penalty reason is required.")

            record_penalty(student_id=student_id, points=points, reason=reason, approved_by=current_user.id)
            db.session.commit()
            flash("Penalty recorded successfully.", "success")
            return redirect(url_for("dashboard.home"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("penalties/form.html", students=students)
