"""
YouTube Video model
"""
from datetime import datetime
from app import db


class YouTubeVideo(db.Model):
    """YouTube Video model"""
    __tablename__ = 'youtube_videos'

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('youtube_channels.id'), nullable=False)
    video_id = db.Column(db.String(100), nullable=False, unique=True)  # YouTube video ID
    title = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.Integer)  # Duration in seconds
    published_at = db.Column(db.DateTime)
    transcript_available = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    topics = db.relationship('Topic', backref='video', lazy='dynamic', foreign_keys='Topic.video_id')

    def __repr__(self):
        return f'<YouTubeVideo {self.video_id}: {self.title}>'
