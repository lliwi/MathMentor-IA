"""
Exercise Usage model - tracks which exercises have been used by which students
"""
from datetime import datetime
from app import db


class ExerciseUsage(db.Model):
    """Track exercise usage to avoid repetition"""
    __tablename__ = 'exercise_usage'

    id = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    used_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('User', backref='exercise_usage_records')

    def __repr__(self):
        return f'<ExerciseUsage exercise_id={self.exercise_id} student_id={self.student_id}>'
