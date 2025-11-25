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

    # Exercise bank management
    status = db.Column(db.String(30), default='auto_generated')  # auto_generated, pending_validation, validated, teacher_created
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Teacher who created/modified
    validated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Teacher who validated
    validated_at = db.Column(db.DateTime, nullable=True)
    modification_notes = db.Column(db.Text, nullable=True)  # Notes about modifications

    # Relationships
    submissions = db.relationship('Submission', backref='exercise', lazy='dynamic', cascade='all, delete-orphan')
    usage_records = db.relationship('ExerciseUsage', backref='exercise', lazy='dynamic', cascade='all, delete-orphan')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_exercises')
    validated_by = db.relationship('User', foreign_keys=[validated_by_id], backref='validated_exercises')

    def __repr__(self):
        return f'<Exercise {self.id} topic={self.topic_id} difficulty={self.difficulty} status={self.status}>'
