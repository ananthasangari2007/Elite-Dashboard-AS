import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db, seed_admin_user
from app.models import PointTransaction, Submission, Task, User
from app.services.catalog import seed_task_catalog


class TestConfig:
    SECRET_KEY = "smoke-test-secret"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{Path(tempfile.gettempdir()) / 'elite_dashboard_smoke.sqlite3'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None


def csrf_token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, html[:500]
    return match.group(1)


def main():
    db_path = Path(tempfile.gettempdir()) / "elite_dashboard_smoke.sqlite3"
    if db_path.exists():
        db_path.unlink()

    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_admin_user()
        student = User(name="Student User", email="student@elite.edu", role="student")
        student.set_password("Student@123")
        db.session.add(student)
        db.session.commit()
        admin = User.query.filter_by(role="admin").first()
        seed_task_catalog(created_by=admin.id if admin else None)

    client = app.test_client()

    response = client.get("/login/admin")
    token = csrf_token(response.get_data(as_text=True))
    response = client.post(
        "/login/admin",
        data={"csrf_token": token, "email": "admin@elite.edu", "password": "Admin@123"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.get("/tasks/create")
    token = csrf_token(response.get_data(as_text=True))
    response = client.post(
        "/tasks/create",
        data={
            "csrf_token": token,
            "title": "Backend Smoke Test Task",
            "description": "Real database task",
            "instructions": "Submit proof",
            "reference_links": "https://example.com",
            "task_type": "weekly",
            "reward_points": "25",
            "status": "active",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        task = Task.query.filter_by(title="Backend Smoke Test Task").order_by(Task.id.desc()).first()
        assert task
        task_id = task.id

    client.get("/logout")
    response = client.get("/login/student")
    token = csrf_token(response.get_data(as_text=True))
    response = client.post(
        "/login/student",
        data={"csrf_token": token, "email": "student@elite.edu", "password": "Student@123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    token = csrf_token(response.get_data(as_text=True))
    response = client.post(
        "/profile/",
        data={
            "csrf_token": token,
            "name": "Student User",
            "register_number": "REG001",
            "department": "CSE",
            "linkedin_url": "https://linkedin.com/in/student",
            "github_url": "https://github.com/student",
            "leetcode_url": "https://leetcode.com/student",
            "preferred_domain": "Web Development",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.get(f"/submissions/task/{task_id}/submit")
    token = csrf_token(response.get_data(as_text=True))
    response = client.post(
        f"/submissions/task/{task_id}/submit",
        data={
            "csrf_token": token,
            "description": "Completed proof",
            "github_link": "https://github.com/example/repo",
            "drive_link": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        submission = Submission.query.filter_by(task_id=task_id).order_by(Submission.id.desc()).first()
        assert submission
        submission_id = submission.id

    client.get("/logout")
    response = client.get("/login/admin")
    token = csrf_token(response.get_data(as_text=True))
    client.post(
        "/login/admin",
        data={"csrf_token": token, "email": "admin@elite.edu", "password": "Admin@123"},
        follow_redirects=True,
    )

    response = client.get("/submissions/pending")
    token = csrf_token(response.get_data(as_text=True))
    response = client.post(
        f"/submissions/{submission_id}/approve",
        data={"csrf_token": token, "remarks": "Approved"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        submission = db.session.get(Submission, submission_id)
        assert submission.status == "approved"
        transaction = PointTransaction.query.filter_by(
            task_id=task_id,
            student_id=submission.student_id,
        ).first()
        assert transaction and transaction.points == 25
        student_id = submission.student_id

    response = client.get(f"/students/{student_id}")
    token = csrf_token(response.get_data(as_text=True))
    response = client.post(
        f"/students/{student_id}/bonus",
        data={"csrf_token": token, "reason": "Daily Top Performer", "points": "20"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.get(f"/students/{student_id}")
    token = csrf_token(response.get_data(as_text=True))
    response = client.post(
        f"/students/{student_id}/penalty",
        data={"csrf_token": token, "reason": "Daily task not updated", "points": "5"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        total = (
            db.session.query(db.func.coalesce(db.func.sum(PointTransaction.points), 0))
            .filter(PointTransaction.student_id == student_id)
            .scalar()
        )
        assert int(total) == 40

    response = client.get("/exports/excel")
    assert response.status_code == 200
    print(f"workflow-ok task={task_id} submission={submission_id}")


if __name__ == "__main__":
    main()
