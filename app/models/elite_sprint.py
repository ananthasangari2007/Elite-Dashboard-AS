from datetime import datetime, timedelta

from app import db


COMPLETION_WINDOW_HOURS = 15


class EliteSprintSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sprint_date = db.Column(db.Date, nullable=False, index=True)
    sprint_type = db.Column(db.String(20), default="overall", nullable=False, index=True)
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    bidding_starts_at = db.Column(db.DateTime, nullable=True, index=True)
    bidding_ends_at = db.Column(db.DateTime, nullable=True, index=True)
    completion_ends_at = db.Column(db.DateTime, nullable=True, index=True)
    status = db.Column(db.String(30), default="active", nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)
    verified = db.Column(db.Boolean, default=False, nullable=False, index=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    verification_mode = db.Column(db.String(20), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by], backref="created_sprint_sessions")
    bids = db.relationship("EliteSprintBid", back_populates="session", cascade="all, delete-orphan")

    @property
    def bidding_start(self):
        return self.bidding_starts_at or self.start_time

    @property
    def bidding_end(self):
        return self.bidding_ends_at or self.end_time

    @property
    def is_open(self):
        now = datetime.utcnow()
        return self.status == "active" and now < (self.bidding_end or self.end_time)

    @property
    def is_bidding_closed(self):
        now = datetime.utcnow()
        end = self.bidding_end or self.end_time
        return bool(end) and now >= end

    @property
    def is_completion_window(self):
        if not self.completion_ends_at:
            return False
        now = datetime.utcnow()
        return not self.verified and now < self.completion_ends_at

    @property
    def completion_remaining_seconds(self):
        if not self.completion_ends_at or self.verified:
            return None
        delta = (self.completion_ends_at - datetime.utcnow()).total_seconds()
        return max(0, int(delta))

    def start_completion_window(self):
        if self.completion_ends_at:
            return False
        bidding_end = self.bidding_ends_at or self.end_time
        if bidding_end:
            self.completion_ends_at = bidding_end + timedelta(hours=COMPLETION_WINDOW_HOURS)
        return True

    def mark_verified(self, mode="manual"):
        self.verified = True
        self.is_verified = True
        self.verified_at = datetime.utcnow()
        self.verification_mode = mode
        self.completion_ends_at = None


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
    task_ids = db.Column(db.JSON, default=list, nullable=False)
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

    @property
    def planned_task_ids(self):
        if self.task_ids:
            return [str(t).upper() for t in self.task_ids]
        combined = (self.daily_tasks or []) + (self.weekly_tasks or []) + (self.monthly_tasks or [])
        return [str(t).upper() for t in combined]
