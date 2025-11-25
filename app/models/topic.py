"""
Topic model
"""
from app import db


class Topic(db.Model):
    """Topic extracted from books or YouTube videos"""
    __tablename__ = 'topics'

    id = db.Column(db.Integer, primary_key=True)

    # Source reference (polymorphic)
    source_type = db.Column(db.String(20), nullable=False, default='pdf_book', server_default='pdf_book')  # 'pdf_book' or 'youtube_video'
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=True)  # Nullable for compatibility
    video_id = db.Column(db.Integer, db.ForeignKey('youtube_videos.id'), nullable=True)

    topic_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)  # Order within the source

    # Relationships
    exercises = db.relationship('Exercise', backref='topic', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Topic {self.topic_name} ({self.source_type})>'
