from app import db


class PointRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream = db.Column(db.String(30), nullable=False, index=True)
    code = db.Column(db.String(30), nullable=False, unique=True, index=True)
    category = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(220), nullable=False)
    points = db.Column(db.Integer, nullable=False)
