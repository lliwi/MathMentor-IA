"""
Submission model
"""
from datetime import datetime
from app import db


class Submission(db.Model):
    """Student exercise submission"""
    __tablename__ = 'submissions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)

    # Student's answer
    answer = db.Column(db.Text, nullable=False)
    methodology = db.Column(db.Text)  # Student's work/steps (legacy)

    # Procedure-based methodology
    selected_procedures = db.Column(db.JSON)  # List of procedure IDs selected by student

    # Evaluation results
    is_correct_result = db.Column(db.Boolean)
    is_correct_methodology = db.Column(db.Boolean)

    # Scoring
    score_result = db.Column(db.Integer, default=0)  # Points for correct result
    score_development = db.Column(db.Integer, default=0)  # Points for correct methodology
    score_effort = db.Column(db.Integer, default=0)  # Points for retry after feedback
    total_score = db.Column(db.Integer, default=0)

    # Feedback
    feedback = db.Column(db.Text)  # AI-generated feedback

    # Retry tracking
    is_retry = db.Column(db.Boolean, default=False)
    parent_submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=True)

    # Timestamps
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Submission student={self.student_id} exercise={self.exercise_id} score={self.total_score}>'
