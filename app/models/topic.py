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

    def get_source_info(self):
        """
        Get formatted source information (book or video)

        Returns:
            dict: Dictionary with source information including title and type
        """
        if self.source_type == 'pdf_book' and self.book:
            return {
                'type': 'book',
                'title': self.book.title,
                'course': self.book.course,
                'subject': self.book.subject,
                'formatted': f"{self.book.title} ({self.book.course} - {self.book.subject})"
            }
        elif self.source_type == 'youtube_video' and self.video:
            return {
                'type': 'video',
                'title': self.video.title,
                'url': self.video.url,
                'channel': self.video.channel.name if self.video.channel else 'Desconocido',
                'formatted': f"{self.video.title} - {self.video.channel.name if self.video.channel else 'Canal desconocido'}"
            }
        else:
            return {
                'type': 'unknown',
                'title': 'Fuente desconocida',
                'formatted': 'Fuente desconocida'
            }

    def __repr__(self):
        return f'<Topic {self.topic_name} ({self.source_type})>'
