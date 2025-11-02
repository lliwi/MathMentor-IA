"""
Topic model
"""
from app import db


class Topic(db.Model):
    """Topic extracted from books"""
    __tablename__ = 'topics'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    topic_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)  # Order within the book

    # Relationships
    exercises = db.relationship('Exercise', backref='topic', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Topic {self.topic_name}>'
