from datetime import datetime

from app import db


class SprintVerificationResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    planned_task_ids = db.Column(db.Text)
    submitted_task_ids = db.Column(db.Text)
    missing_task_ids = db.Column(db.Text)
    penalty_points = db.Column(db.Integer, default=0)
    earned_golden_star = db.Column(db.Boolean, default=False, nullable=False)
    verified_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_sprint_verify_session_student"),
    )

    student = db.relationship("User", foreign_keys=[student_id], backref="sprint_verification_results")

    @staticmethod
    def parse_ids(value):
        if not value:
            return []
        return [part.strip().upper() for part in value.split(",") if part.strip()]

    @property
    def is_golden_star(self):
        return bool(self.earned_golden_star)

    @property
    def has_penalty(self):
        return self.penalty_points > 0 or bool(self.missing_task_ids)
