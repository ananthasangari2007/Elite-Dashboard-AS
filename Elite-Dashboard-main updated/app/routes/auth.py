from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app import db
from app.models import User


auth_bp = Blueprint("auth", __name__)


PORTALS = {
    "admin": {
        "label": "Admin Portal",
        "role": "admin",
        "hint": "Command center for batches, tasks, approvals, analytics, and reports.",
    },
    "student": {
        "label": "Student Portal",
        "role": "student",
        "hint": "View tasks, submit work, follow progress, and climb the leaderboard.",
    },
}


@auth_bp.route("/")
def choose_portal():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    return render_template("auth/choose_portal.html", portals=PORTALS)


@auth_bp.route("/login/<portal>", methods=["GET", "POST"])
def login(portal):
    portal_config = PORTALS.get(portal)
    if not portal_config:
        flash("Choose a valid portal to continue.", "warning")
        return redirect(url_for("auth.choose_portal"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        user = User.query.filter_by(email=email, role=portal_config["role"]).first()

        if user and user.check_password(password):
            if user.role == "student" and user.approval_status != "approved":
                flash("Your account is waiting for admin approval.", "warning")
                return render_template("auth/login.html", portal=portal, portal_config=portal_config)

            login_user(user, remember=True if user.role == "student" else remember)
            flash(f"Welcome back, {user.name}.", "success")
            if user.role == "student" and not user.profile_completed:
                return redirect(url_for("profile.edit"))
            return redirect(url_for("dashboard.home"))

        flash("Login failed. Use the matching demo email and password for this portal.", "danger")

    return render_template("auth/login.html", portal=portal, portal_config=portal_config)


@auth_bp.route("/register/student", methods=["GET", "POST"])
def register_student():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not name:
                raise ValueError("Name is required.")
            if not email:
                raise ValueError("College email is required.")
            if len(password) < 8:
                raise ValueError("Password must contain at least 8 characters.")
            if User.query.filter_by(email=email).first():
                raise ValueError("This email is already registered.")

            user = User(name=name, email=email, role="student", approval_status="pending")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created. Your registration is pending admin approval.", "success")
            return redirect(url_for("auth.login", portal="student"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("auth/register_student.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.choose_portal"))
