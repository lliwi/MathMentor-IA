"""
User model
"""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db


class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # 'admin', 'teacher', or 'student'
    centro = db.Column(db.String(200), nullable=True)  # Educational center/school name
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    student_profile = db.relationship('StudentProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    submissions = db.relationship('Submission', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    student_score = db.relationship('StudentScore', backref='student', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if password matches hash"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
