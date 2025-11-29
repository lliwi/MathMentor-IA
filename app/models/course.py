"""
Course model
"""
from app import db


class Course(db.Model):
    """Course/Grade level model"""
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # e.g., "1º ESO", "2º Bachillerato"
    order = db.Column(db.Integer, nullable=False, default=0)  # For display ordering
    active = db.Column(db.Boolean, default=True)  # Enable/disable courses

    def __repr__(self):
        return f'<Course {self.name}>'
