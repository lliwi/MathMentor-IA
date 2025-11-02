"""
Database models
"""
from app.models.user import User
from app.models.student_profile import StudentProfile
from app.models.book import Book
from app.models.topic import Topic
from app.models.exercise import Exercise
from app.models.submission import Submission
from app.models.student_score import StudentScore
from app.models.document_embedding import DocumentEmbedding

__all__ = [
    'User',
    'StudentProfile',
    'Book',
    'Topic',
    'Exercise',
    'Submission',
    'StudentScore',
    'DocumentEmbedding'
]
