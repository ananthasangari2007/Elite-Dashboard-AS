from datetime import datetime

from app import db


class EliteSprintSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sprint_date = db.Column(db.Date, nullable=False, index=True)
    sprint_type = db.Column(db.String(20), default="overall", nullable=False, index=True)
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(30), default="active", nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by], backref="created_sprint_sessions")
    bids = db.relationship("EliteSprintBid", back_populates="session", cascade="all, delete-orphan")

    @property
    def is_open(self):
        now = datetime.utcnow()
        return self.status == "active" and now < self.end_time


class EliteSprintBid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("elite_sprint_session.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    daily_count = db.Column(db.Integer, default=0, nullable=False)
    weekly_count = db.Column(db.Integer, default=0, nullable=False)
    monthly_count = db.Column(db.Integer, default=0, nullable=False)
    daily_tasks = db.Column(db.JSON, default=list, nullable=False)
    weekly_tasks = db.Column(db.JSON, default=list, nullable=False)
    monthly_tasks = db.Column(db.JSON, default=list, nullable=False)
    is_locked = db.Column(db.Boolean, default=False, nullable=False, index=True)
    locked_at = db.Column(db.DateTime, nullable=True)
    has_golden_star = db.Column(db.Boolean, default=False, nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    session = db.relationship("EliteSprintSession", back_populates="bids")
    student = db.relationship("User", foreign_keys=[student_id], backref="elite_sprint_bids")

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_elite_sprint_bid_session_student"),
    )

    @property
    def total_tasks_bidded(self):
        return int(self.daily_count or 0) + int(self.weekly_count or 0) + int(self.monthly_count or 0)
