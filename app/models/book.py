"""
Book model
"""
from datetime import datetime
from app import db


class Book(db.Model):
    """Book/Textbook model"""
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    course = db.Column(db.String(100), nullable=False)  # e.g., "1º ESO"
    subject = db.Column(db.String(100), nullable=False)  # e.g., "Matemáticas"
    pdf_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed = db.Column(db.Boolean, default=False)  # RAG processing status

    # Relationships
    topics = db.relationship('Topic', backref='book', lazy='dynamic', cascade='all, delete-orphan')
    embeddings = db.relationship('DocumentEmbedding', backref='book', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Book {self.title} ({self.course} - {self.subject})>'
