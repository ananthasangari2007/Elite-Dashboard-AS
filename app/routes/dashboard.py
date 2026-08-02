from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models import PointTransaction, Submission, Task, User
from app.services.elite_sprint import get_active_session, latest_session as get_latest_sprint, sprint_leaderboard
from app.services.points import leaderboard, monthly_points_query, overall_points_query, total_points_awarded
from app.services.submissions import current_daily_streak, dashboard_submission_analytics, top_daily_streaks


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/charts/data")
@login_required
def chart_data():
    if current_user.role == "admin":
        top_students = overall_points_query().order_by(db.desc("overall_points"), User.name.asc()).limit(8).all()
        task_distribution = (
            db.session.query(Task.task_type, func.count(Task.id).label("count"))
            .filter(Task.status == "active")
            .group_by(Task.task_type)
            .all()
        )
        trend_rows = (
            db.session.query(Submission.submission_date, func.count(Submission.id).label("count"))
            .filter(Submission.status == "approved")
            .group_by(Submission.submission_date)
            .order_by(Submission.submission_date.asc())
            .limit(7)
            .all()
        )
        submission_status = (
            db.session.query(Submission.status, func.count(Submission.id).label("count"))
            .group_by(Submission.status)
            .all()
        )
        task_performance = (
            db.session.query(
                Task.id.label("task_id"),
                Task.task_code.label("task_code"),
                func.coalesce(
                    func.sum(db.case((Submission.status == "approved", 1), else_=0)),
                    0,
                ).label("approved_count"),
            )
            .outerjoin(Submission, Submission.task_id == Task.id)
            .filter(Task.status == "active")
            .group_by(Task.id, Task.task_code)
            .order_by(Task.created_at.asc())
            .all()
        )
        return jsonify(
            {
                "role": "admin",
                "top_students": {
                    "labels": [row.student_name for row in top_students],
                    "values": [int(row.overall_points or 0) for row in top_students],
                },
                "task_distribution": {
                    "labels": [row.task_type.title() for row in task_distribution],
                    "values": [row.count for row in task_distribution],
                },
                "approval_trend": {
                    "labels": [row.submission_date.strftime("%d %b") for row in trend_rows],
                    "values": [row.count for row in trend_rows],
                },
                "submission_status": {
                    "labels": [row.status.replace("_", " ").title() for row in submission_status],
                    "values": [row.count for row in submission_status],
                },
                "task_performance": {
                    "labels": [row.task_code or f"Task {row.task_id}" for row in task_performance],
                    "values": [int(row.approved_count or 0) for row in task_performance],
                },
            }
        )

    return jsonify({"role": "student", "charts": []})


@dashboard_bp.route("/")
@login_required
def home():
    active_sprint = get_active_session()
    latest_sprint = active_sprint or get_latest_sprint()
    active_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()
    leaderboard_rows = leaderboard(limit=10)
    pending_approvals = Submission.query.filter_by(status="waiting_approval").count()
    category_counts = {
        "daily": Task.query.filter_by(task_type="daily", status="active").count(),
        "weekly": Task.query.filter_by(task_type="weekly", status="active").count(),
        "monthly": Task.query.filter_by(task_type="monthly", status="active").count(),
    }
    completed_submissions = []
    performance_rows = []
    submission_analytics = dashboard_submission_analytics()
    streak_rows = top_daily_streaks(limit=5)
    daily_streak = 0

    if current_user.role == "student":
        daily_streak = current_daily_streak(current_user.id)
        status_counts = {
            "waiting_approval": Submission.query.filter_by(student_id=current_user.id, status="waiting_approval").count(),
            "approved": Submission.query.filter_by(student_id=current_user.id, status="approved").count(),
            "rejected": Submission.query.filter_by(student_id=current_user.id, status="rejected").count(),
        }
        submitted_task_ids = {
            row.task_id for row in Submission.query.filter_by(student_id=current_user.id).with_entities(Submission.task_id).all()
        }
        assigned_count = Task.query.filter_by(status="active").count()
        pending_tasks = max(assigned_count - len(submitted_task_ids), 0)
        overall_row = overall_points_query().filter(User.id == current_user.id).first()
        monthly_row = monthly_points_query().filter(User.id == current_user.id).first()
        monthly_total = int(monthly_row.monthly_points or 0) if monthly_row else 0
        metrics = [
            {"label": "Assigned Tasks", "value": assigned_count, "detail": f"{pending_tasks} task(s) waiting for proof", "tone": "blue"},
            {"label": "Task Status", "value": status_counts["waiting_approval"], "detail": "waiting for admin approval", "tone": "amber"},
            {"label": "Overall Points", "value": int(overall_row.overall_points or 0) if overall_row else 0, "detail": "from awards and penalties", "tone": "violet"},
            {"label": "Monthly Points", "value": monthly_total, "detail": "current month net score", "tone": "green"},
            {"label": "Daily Streak", "value": daily_streak, "detail": "approved submission days in a row", "tone": "amber"},
        ]
        completed_submissions = (
            Submission.query.filter_by(student_id=current_user.id, status="approved")
            .order_by(Submission.reviewed_at.desc())
            .limit(5)
            .all()
        )
    else:
        student_count = User.query.filter_by(role="student").count()
        task_count = Task.query.count()
        transaction_count = PointTransaction.query.count()
        metrics = [
            {"label": "Total Students", "value": student_count, "detail": "registered student accounts", "tone": "blue"},
            {"label": "Total Tasks", "value": task_count, "detail": "tasks stored in database", "tone": "amber"},
            {"label": "Pending Approvals", "value": pending_approvals, "detail": "submissions waiting for review", "tone": "green"},
            {"label": "Overall Points", "value": total_points_awarded(), "detail": f"{transaction_count} point transactions", "tone": "violet"},
            {"label": "Today's Submissions", "value": submission_analytics["today_submissions"], "detail": "proofs submitted today", "tone": "blue"},
            {"label": "Students Today", "value": submission_analytics["unique_students_today"], "detail": "unique students submitted", "tone": "green"},
            {"label": "Weekly Average", "value": submission_analytics["average_submissions_per_student_week"], "detail": "submissions per active student", "tone": "violet"},
        ]
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)
        month_end = datetime(now.year + 1, 1, 1) if now.month == 12 else datetime(now.year, now.month + 1, 1)
        monthly_total = (
            db.session.query(func.coalesce(func.sum(PointTransaction.points), 0))
            .filter(PointTransaction.created_at >= month_start, PointTransaction.created_at < month_end)
            .scalar()
            or 0
        )
        performance_rows = leaderboard(limit=10)
    sprint_board = sprint_leaderboard(latest_sprint.id, limit=5) if latest_sprint else []

    return render_template(
        "dashboard/home.html",
        active_sprint=active_sprint,
        latest_sprint=latest_sprint,
        sprint_board=sprint_board,
        submission_analytics=submission_analytics,
        streak_rows=streak_rows,
        daily_streak=daily_streak,
        metrics=metrics,
        tasks=active_tasks,
        leaderboard=leaderboard_rows,
        monthly_total=int(monthly_total),
        pending_approvals=pending_approvals,
        category_counts=category_counts,
        completed_submissions=completed_submissions,
        performance_rows=performance_rows,
    )
