import os
from pathlib import Path

import click
from flask import Flask, redirect, request, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import text

from config import Config


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql"):
            repairs = [
                "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE",
                "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP",
                "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS verification_due_at TIMESTAMP",
                "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
                "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP",
                "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS has_golden_star BOOLEAN DEFAULT FALSE",
                "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS penalty_points INTEGER DEFAULT 0",
                "ALTER TABLE elite_sprint_bid ADD COLUMN IF NOT EXISTS penalty_reason VARCHAR(255)",
                'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS has_active_sprint_penalty BOOLEAN DEFAULT FALSE',
                'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS golden_stars INTEGER DEFAULT 0',
                'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS penalty_flags INTEGER DEFAULT 0',
                "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS sprint_mode VARCHAR(20) DEFAULT 'overall'",
                "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'scheduled'",
                "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS created_by INTEGER",
                "ALTER TABLE elite_sprint_session ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            ]

            for sql in repairs:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    print(f"Schema repair skipped: {exc}")

            print("PostgreSQL schema auto-repair completed.")

    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.choose_portal"
    csrf.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.exports import exports_bp
    from app.routes.penalties import penalties_bp
    from app.routes.profile import profile_bp
    from app.routes.students import students_bp
    from app.routes.submissions import submissions_bp
    from app.routes.support import support_bp
    from app.routes.tasks import tasks_bp
    from app.routes.elite_sprint import elite_sprint_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(submissions_bp)
    app.register_blueprint(penalties_bp)
    app.register_blueprint(exports_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(elite_sprint_bp)
    register_cli(app)
    register_sprint_status_guard(app)
    register_profile_guard(app)

    return app


def register_profile_guard(app):
    @app.before_request
    def require_student_profile():
        if not current_user.is_authenticated:
            return None
        if current_user.role != "student" or current_user.profile_completed:
            return None
        allowed_endpoints = {"profile.edit", "auth.logout", "static"}
        if request.endpoint in allowed_endpoints:
            return None
        return redirect(url_for("profile.edit"))


def register_sprint_status_guard(app):
    @app.before_request
    def close_elapsed_sprint_sessions():
        from app.services.elite_sprint import process_expired_sprint_verifications

        try:
            process_expired_sprint_verifications()
        except Exception:
            db.session.rollback()


def get_initial_admin_password():
    password = os.getenv("ADMIN_PASSWORD") or os.getenv("INITIAL_ADMIN_PASSWORD")
    if password:
        return password
    if (os.getenv("FLASK_ENV") or "development").lower() in {"production", "prod", "staging"}:
        raise RuntimeError("ADMIN_PASSWORD or INITIAL_ADMIN_PASSWORD must be set in production")
    return "Admin@123"


def seed_admin_user():
    from app.models import User

    email = "admin@elite.edu"
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(name="Super Admin", email=email, role="admin", profile_completed=True)
        user.set_password(get_initial_admin_password())
        db.session.add(user)

    db.session.commit()


def register_cli(app):
    @app.cli.command("seed-admin")
    def seed_admin():
        seed_admin_user()
        click.echo("Admin user is ready.")

    @app.cli.command("create-admin")
    @click.argument('email')
    @click.option('--password', default=None, help='Password for the new admin')
    def create_admin(email, password):
        """Create a single admin user: flask create-admin admin@example.com --password Secret"""
        from app.models import User

        if password is None:
            password = get_initial_admin_password()

        user = User.query.filter_by(email=email).first()
        if user:
            click.echo(f"User with email {email} already exists.")
            return
        user = User(name="Super Admin", email=email, role="admin", profile_completed=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin {email} created.")

    @app.cli.command("reset-admin-password")
    @click.argument("email")
    @click.option("--password", default=None, help="New password for the admin account")
    def reset_admin_password(email, password):
        """Reset an existing admin password without changing portal data."""
        from app.models import User

        password = password or get_initial_admin_password()
        user = User.query.filter_by(email=email, role="admin").first()
        if not user:
            click.echo(f"Admin {email} was not found.")
            return
        user.set_password(password)
        db.session.commit()
        click.echo(f"Password reset for admin {email}.")

    @app.cli.command("seed-task-catalog")
    def seed_task_catalog_command():
        from app.models import User
        from app.services.catalog import seed_task_catalog

        admin = User.query.filter_by(role="admin").first()
        seed_task_catalog(created_by=admin.id if admin else None)
        click.echo("Task catalog is ready.")

    @app.cli.command("seed-tasks")
    def seed_tasks_command():
        """Alias for seeding the task catalog: flask seed-tasks"""
        from app.services.catalog import seed_task_catalog
        from app.models import User

        admin = User.query.filter_by(role="admin").first()
        seed_task_catalog(created_by=admin.id if admin else None)
        click.echo("Task catalog is ready.")
