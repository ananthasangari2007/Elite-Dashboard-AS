from datetime import datetime

from app import db


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_code = db.Column(db.String(30), unique=True, index=True)
    category = db.Column(db.String(120), index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    reference_links = db.Column(db.Text)
    reward_points = db.Column(db.Integer, default=0, nullable=False)
    task_type = db.Column(db.String(20), default="daily", nullable=False, index=True)
    status = db.Column(db.String(30), default="active", nullable=False, index=True)
    attachment_path = db.Column(db.String(500))
    start_at = db.Column(db.DateTime)
    due_at = db.Column(db.DateTime)
    deadline_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])
