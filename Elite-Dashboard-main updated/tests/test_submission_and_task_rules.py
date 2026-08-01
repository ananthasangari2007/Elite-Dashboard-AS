import os
import tempfile
from datetime import datetime, timedelta

from sqlalchemy import func

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.gettempdir()}/elite_dashboard_test.db")

from app import create_app, db
from app.models import Submission, Task, User
from app.services.submissions import can_submit_task_on_date


def setup_app():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()

        student = User(name="Test Student", email="student@test.com", role="student", approval_status="approved")
        student.set_password("secret123")
        admin = User(name="Test Admin", email="admin@test.com", role="admin", approval_status="approved")
        admin.set_password("secret123")
        db.session.add_all([student, admin])
        db.session.commit()

        task = Task(
            title="Daily Task",
            task_code="D101",
            task_type="daily",
            reward_points=50,
            status="active",
            created_at=datetime.utcnow() - timedelta(days=2),
            created_by=admin.id,
        )
        task2 = Task(
            title="Another Daily Task",
            task_code="D102",
            task_type="daily",
            reward_points=40,
            status="active",
            created_at=datetime.utcnow() - timedelta(days=1),
            created_by=admin.id,
        )
        db.session.add_all([task, task2])
        db.session.commit()

        student_id = student.id
        task_id = task.id
        task2_id = task2.id

    return app, student_id, task_id, task2_id


def test_rejected_submission_allows_same_day_resubmission():
    app, student_id, task_id, _ = setup_app()
    with app.app_context():
        today = datetime.utcnow().date()
        db.session.add(
            Submission(
                student_id=student_id,
                task_id=task_id,
                submission_date=today,
                status="rejected",
                description="retry",
                submitted_at=datetime.utcnow(),
            )
        )
        db.session.commit()

        allowed, message = can_submit_task_on_date(student_id, task_id, today)

        assert allowed is True
        assert message is None


def test_approved_submission_blocks_duplicate_same_day():
    app, student_id, task_id, _ = setup_app()
    with app.app_context():
        today = datetime.utcnow().date()
        db.session.add(
            Submission(
                student_id=student_id,
                task_id=task_id,
                submission_date=today,
                status="approved",
                description="already done",
                submitted_at=datetime.utcnow(),
                approved_at=datetime.utcnow(),
            )
        )
        db.session.commit()

        allowed, message = can_submit_task_on_date(student_id, task_id, today)

        assert allowed is False
        assert "already approved" in message.lower()


def test_daily_tasks_are_ordered_by_creation_time():
    app, _, _, _ = setup_app()
    with app.app_context():
        tasks = Task.query.filter_by(task_type="daily").order_by(Task.created_at.asc()).all()
        assert [task.task_code for task in tasks] == ["D101", "D102"]
