"""
Hint Purchase model
"""
from datetime import datetime
from app import db


class HintPurchase(db.Model):
    """
    Model to track hint purchases by students.

    Each hint purchase creates a new record to maintain complete history.
    """
    __tablename__ = 'hint_purchases'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)

    # Hint details
    hint_level = db.Column(db.Integer, nullable=False)  # 1 (text) or 2 (visual)
    hint_type = db.Column(db.String(20))  # 'text' or 'visual'
    points_paid = db.Column(db.Integer, default=5)  # Cost of hint (always 5)

    # Timestamp
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('User', backref='hint_purchases')
    exercise = db.relationship('Exercise', backref='hint_purchases')

    def __repr__(self):
        return f'<HintPurchase Student {self.student_id} - Exercise {self.exercise_id} - Level {self.hint_level}>'
