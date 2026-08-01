from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.utils.auth import role_required


profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.route("/", methods=["GET", "POST"])
@role_required("student")
def edit():
    if request.method == "POST":
        try:
            current_user.name = request.form.get("name", "").strip()
            current_user.register_number = request.form.get("register_number", "").strip()
            current_user.department = request.form.get("department", "").strip()
            current_user.linkedin_url = request.form.get("linkedin_url", "").strip()
            current_user.github_url = request.form.get("github_url", "").strip()
            current_user.leetcode_url = request.form.get("leetcode_url", "").strip()
            current_user.preferred_domain = request.form.get("preferred_domain", "").strip()

            if not current_user.name:
                raise ValueError("Name is required.")
            if not current_user.register_number:
                raise ValueError("Register number is required.")
            if not current_user.department:
                raise ValueError("Department is required.")

            current_user.profile_completed = True
            db.session.commit()
            flash("Profile details updated successfully.", "success")
            return redirect(url_for("dashboard.home"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("profile/edit.html")
