"""
Exercise model
"""
from datetime import datetime
from app import db


class Exercise(db.Model):
    """Generated exercise"""
    __tablename__ = 'exercises'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)  # The exercise question/problem
    solution = db.Column(db.Text)  # Expected solution
    methodology = db.Column(db.Text)  # Expected step-by-step solution (legacy)

    # Procedure-based methodology
    available_procedures = db.Column(db.JSON)  # List of all procedures/techniques for this exercise
    expected_procedures = db.Column(db.JSON)  # List of procedure IDs that should be selected

    difficulty = db.Column(db.String(20), default='medium')  # easy, medium, hard
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    submissions = db.relationship('Submission', backref='exercise', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Exercise {self.id} topic={self.topic_id} difficulty={self.difficulty}>'
