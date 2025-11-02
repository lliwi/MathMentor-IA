"""
Document Embedding model for RAG
"""
from app import db
from pgvector.sqlalchemy import Vector


class DocumentEmbedding(db.Model):
    """Document embeddings for RAG (Retrieval-Augmented Generation)"""
    __tablename__ = 'document_embeddings'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)

    # Content
    chunk_text = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer)  # Position in the document
    page_number = db.Column(db.Integer)  # Page number in PDF

    # Embedding vector (dimension depends on model, typically 384 or 768)
    embedding = db.Column(Vector(384))  # Using 384 for all-MiniLM-L6-v2

    # Metadata
    topic_reference = db.Column(db.String(200))  # Related topic if identified

    def __repr__(self):
        return f'<DocumentEmbedding book={self.book_id} chunk={self.chunk_index}>'
