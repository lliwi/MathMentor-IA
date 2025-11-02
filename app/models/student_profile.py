"""
Student Profile model
"""
from app import db


class StudentProfile(db.Model):
    """Student profile with course and assigned topics"""
    __tablename__ = 'student_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    course = db.Column(db.String(100), nullable=False)  # e.g., "1º ESO", "2º Bachillerato"
    topics_assigned = db.Column(db.Text)  # JSON string of assigned topic IDs

    def __repr__(self):
        return f'<StudentProfile user_id={self.user_id} course={self.course}>'

    def get_topics(self):
        """Parse and return assigned topics as list"""
        import json
        if self.topics_assigned:
            try:
                return json.loads(self.topics_assigned)
            except:
                return []
        return []

    def set_topics(self, topic_ids):
        """Set topics as JSON string"""
        import json
        self.topics_assigned = json.dumps(topic_ids)
