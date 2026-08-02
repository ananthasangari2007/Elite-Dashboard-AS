from datetime import datetime

from app import db


class SupportMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    subject = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="open", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("User", backref="support_messages")
