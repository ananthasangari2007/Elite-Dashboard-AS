from datetime import datetime

from app import db


class PointTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=True, index=True)
    type = db.Column(db.String(20), nullable=False, index=True)
    points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    student = db.relationship("User", foreign_keys=[student_id], backref="point_transactions")
    task = db.relationship("Task", backref="point_transactions")
    approver = db.relationship("User", foreign_keys=[approved_by])

    @staticmethod
    def award(student_id, points, reason, task_id=None, approved_by=None):
        return PointTransaction(
            student_id=student_id,
            task_id=task_id,
            type="award",
            points=abs(int(points)),
            reason=reason,
            approved_by=approved_by,
        )

    @staticmethod
    def penalty(student_id, points, reason, approved_by=None):
        return PointTransaction(
            student_id=student_id,
            task_id=None,
            type="penalty",
            points=-abs(int(points)),
            reason=reason,
            approved_by=approved_by,
        )
