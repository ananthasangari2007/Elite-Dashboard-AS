from datetime import datetime, timedelta, time

from app import db


def _to_time(value):
    if value is None:
        return time(0, 0)
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    return value


class EliteSprintSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sprint_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    sprint_mode = db.Column(db.String(20), nullable=False, default="overall")
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    bids = db.relationship("EliteSprintBid", back_populates="session", cascade="all, delete-orphan")

    @property
    def start_datetime(self):
        return datetime.combine(self.sprint_date, _to_time(self.start_time))

    @property
    def end_datetime(self):
        return datetime.combine(self.sprint_date, _to_time(self.end_time))

    @property
    def is_open(self):
        now = datetime.utcnow()
        return self.start_datetime <= now < self.end_datetime

    @property
    def is_expired(self):
        now = datetime.utcnow()
        return now >= self.end_datetime


class EliteSprintBid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("elite_sprint_session.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    is_locked = db.Column(db.Boolean, default=False, nullable=False, index=True)
    locked_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    verification_due_at = db.Column(db.DateTime, nullable=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    has_golden_star = db.Column(db.Boolean, default=False, nullable=False, index=True)
    penalty_points = db.Column(db.Integer, default=0, nullable=False)
    penalty_reason = db.Column(db.Text, nullable=True)

    session = db.relationship("EliteSprintSession", back_populates="bids")
    student = db.relationship("User", foreign_keys=[student_id], backref="elite_sprint_bids")
    tasks = db.relationship("EliteSprintBidTask", back_populates="bid", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_elite_sprint_bid_session_student"),
    )

    @property
    def planned_task_ids(self):
        return [bt.task_id for bt in self.tasks]


class EliteSprintBidTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bid_id = db.Column(db.Integer, db.ForeignKey("elite_sprint_bid.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False)

    bid = db.relationship("EliteSprintBid", back_populates="tasks")
    task = db.relationship("Task")