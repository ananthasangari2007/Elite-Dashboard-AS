from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True, index=True)
    role = db.Column(db.String(30), nullable=False, index=True)
    approval_status = db.Column(db.String(30), default="approved", nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    has_active_sprint_penalty = db.Column(db.Boolean, default=False, nullable=False, index=True)
    profile_completed = db.Column(db.Boolean, default=False, nullable=False)
    register_number = db.Column(db.String(80), index=True)
    department = db.Column(db.String(120), index=True)
    linkedin_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    leetcode_url = db.Column(db.String(500))
    preferred_domain = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def is_active(self):
        return self.is_active_account

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
