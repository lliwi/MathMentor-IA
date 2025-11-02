"""
Student Score model
"""
from datetime import datetime
from app import db


class StudentScore(db.Model):
    """Student total score and streak tracking"""
    __tablename__ = 'student_scores'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)

    # Points
    total_points = db.Column(db.Integer, default=0)
    points_spent = db.Column(db.Integer, default=0)  # Points spent on hints
    available_points = db.Column(db.Integer, default=0)  # total_points - points_spent

    # Streak tracking
    current_streak = db.Column(db.Integer, default=0)
    best_streak = db.Column(db.Integer, default=0)
    last_exercise_date = db.Column(db.DateTime)

    # Statistics
    total_exercises = db.Column(db.Integer, default=0)
    correct_exercises = db.Column(db.Integer, default=0)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<StudentScore student={self.student_id} points={self.available_points} streak={self.current_streak}>'

    def add_points(self, points):
        """Add points to student score"""
        self.total_points += points
        self.available_points = self.total_points - self.points_spent
        self.updated_at = datetime.utcnow()

    def spend_points(self, points):
        """Spend points (for hints)"""
        if self.available_points >= points:
            self.points_spent += points
            self.available_points = self.total_points - self.points_spent
            self.updated_at = datetime.utcnow()
            return True
        return False

    def update_streak(self, is_correct):
        """Update streak based on exercise result"""
        if is_correct:
            self.current_streak += 1
            if self.current_streak > self.best_streak:
                self.best_streak = self.current_streak
        else:
            self.current_streak = 0

        self.last_exercise_date = datetime.utcnow()
        self.updated_at = datetime.utcnow()
