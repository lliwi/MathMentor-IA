"""
YouTube Channel model
"""
from datetime import datetime
from app import db


class YouTubeChannel(db.Model):
    """YouTube Channel model"""
    __tablename__ = 'youtube_channels'

    id = db.Column(db.Integer, primary_key=True)
    channel_url = db.Column(db.String(500), nullable=False, unique=True)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_count = db.Column(db.Integer, default=0)
    course = db.Column(db.String(100), nullable=False)  # e.g., "1º ESO"
    subject = db.Column(db.String(100), nullable=False, default="Matemáticas")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed = db.Column(db.Boolean, default=False)  # Processing status

    # Relationships
    videos = db.relationship('YouTubeVideo', backref='channel', lazy='dynamic', cascade='all, delete-orphan')
    embeddings = db.relationship('VideoEmbedding', backref='channel', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<YouTubeChannel {self.channel_name} ({self.course} - {self.subject})>'
