from datetime import datetime
from app import db


class SummaryUsage(db.Model):
    """
    Model to track summary access by students.

    This enables:
    - Re-access tracking (free unlimited access after first purchase)
    - Usage statistics
    - Prevention of duplicate purchases
    """
    __tablename__ = 'summary_usage'

    id = db.Column(db.Integer, primary_key=True)
    summary_id = db.Column(db.Integer, db.ForeignKey('summaries.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Access tracking
    first_accessed_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed_at = db.Column(db.DateTime, default=datetime.utcnow)
    access_count = db.Column(db.Integer, default=1)
    points_paid = db.Column(db.Integer, default=15)  # Always 15 for first purchase

    # Relationships
    student = db.relationship('User', backref='summary_usage_records')

    # Unique constraint: one record per student-summary pair
    __table_args__ = (
        db.UniqueConstraint('summary_id', 'student_id', name='uq_summary_student'),
    )

    def __repr__(self):
        return f'<SummaryUsage Student {self.student_id} - Summary {self.summary_id} - Accesses {self.access_count}>'

    def update_access(self):
        """Update last_accessed_at and increment access_count"""
        self.last_accessed_at = datetime.utcnow()
        self.access_count += 1
