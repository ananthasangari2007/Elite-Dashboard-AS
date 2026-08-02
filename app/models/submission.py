from datetime import datetime

from app import db


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    proof_url = db.Column(db.String(700))
    github_link = db.Column(db.String(500))
    drive_link = db.Column(db.String(500))
    file_path = db.Column(db.String(500))
    status = db.Column(db.String(30), default="waiting_approval", nullable=False, index=True)
    admin_remarks = db.Column(db.Text)
    submission_date = db.Column(db.Date, default=lambda: datetime.utcnow().date(), nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime, index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    sprint_session_id = db.Column(db.Integer, db.ForeignKey("elite_sprint_session.id"), nullable=True, index=True)

    student = db.relationship("User", foreign_keys=[student_id], backref="submissions")
    task = db.relationship("Task", backref=db.backref("submissions", cascade="all, delete-orphan"))
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    sprint_session = db.relationship(
        "EliteSprintSession", foreign_keys=[sprint_session_id],
        backref=db.backref("sprint_submissions"),
    )

    __table_args__ = (
        db.Index(
            "ix_submission_student_task_date_status",
            "student_id",
            "task_id",
            "submission_date",
            "status",
        ),
    )
