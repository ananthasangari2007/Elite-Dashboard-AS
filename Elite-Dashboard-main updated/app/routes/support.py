from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.models import SupportMessage
from app.utils.auth import role_required


support_bp = Blueprint("support", __name__, url_prefix="/support")


@support_bp.route("/contact", methods=["GET", "POST"])
@role_required("student")
def contact():
    if request.method == "POST":
        try:
            subject = request.form.get("subject", "").strip()
            message = request.form.get("message", "").strip()
            if not subject:
                raise ValueError("Subject is required.")
            if not message:
                raise ValueError("Message is required.")

            db.session.add(SupportMessage(student_id=current_user.id, subject=subject, message=message))
            db.session.commit()
            flash("Your support message was sent to admin.", "success")
            return redirect(url_for("dashboard.home"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("support/contact.html")


@support_bp.route("/admin")
@role_required("admin")
def admin_inbox():
    messages = SupportMessage.query.order_by(SupportMessage.created_at.desc()).all()
    return render_template("support/admin.html", messages=messages)
