from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    has_access = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text)
    image_url = db.Column(db.String(500))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    order_ref = db.Column(db.String(64), unique=True)
    amount_rupees = db.Column(db.Float)
    # pending -> QR shown, no UTR submitted yet
    # submitted -> buyer says they paid, UTR on file, awaiting your check
    # verified -> you approved it and access was granted
    # rejected -> UTR didn't check out
    status = db.Column(db.String(20), default="pending")
    utr_number = db.Column(db.String(64))
    submitted_at = db.Column(db.DateTime)
    verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
