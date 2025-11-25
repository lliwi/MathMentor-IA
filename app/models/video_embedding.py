"""
Video Embedding model for RAG
"""
from app import db
from pgvector.sqlalchemy import Vector


class VideoEmbedding(db.Model):
    """Video embeddings for RAG (Retrieval-Augmented Generation)"""
    __tablename__ = 'video_embeddings'

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('youtube_channels.id'), nullable=False)
    video_id = db.Column(db.String(100), nullable=False)  # YouTube video ID

    # Content
    chunk_text = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer)  # Position in the video transcript
    timestamp = db.Column(db.String(20))  # Format: "MM:SS" or "HH:MM:SS"

    # Embedding vector (dimension 384 for all-MiniLM-L6-v2)
    embedding = db.Column(Vector(384))

    # Metadata
    topic_reference = db.Column(db.String(200))  # Related topic if identified

    def __repr__(self):
        return f'<VideoEmbedding video={self.video_id} chunk={self.chunk_index}>'
