"""
RAG (Retrieval-Augmented Generation) Service
"""
import os
import numpy as np
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from app import db
from app.models.document_embedding import DocumentEmbedding
from app.models.book import Book
from app.models.topic import Topic


class RAGService:
    """Service for RAG operations (embedding and retrieval)"""

    def __init__(self, model_name: str = None):
        """
        Initialize RAG Service

        Args:
            model_name: Name of the sentence-transformer model
        """
        self.model_name = model_name or os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        embedding = self.model.encode(text)
        return embedding.tolist()

    def store_chunks(self, book_id: int, chunks: List[Dict[str, any]]) -> int:
        """
        Generate embeddings and store chunks in database

        Args:
            book_id: ID of the book
            chunks: List of chunk dicts from PDFProcessor

        Returns:
            Number of chunks stored
        """
        stored_count = 0

        for chunk in chunks:
            # Generate embedding
            embedding = self.generate_embedding(chunk['text'])

            # Create database entry
            doc_embedding = DocumentEmbedding(
                book_id=book_id,
                chunk_text=chunk['text'],
                chunk_index=chunk['chunk_index'],
                page_number=chunk['page_number'],
                embedding=embedding
            )

            db.session.add(doc_embedding)
            stored_count += 1

        db.session.commit()
        return stored_count

    def retrieve_context(self, query: str, book_id: int = None, topic_id: int = None,
                        top_k: int = 3) -> List[Tuple[str, float]]:
        """
        Retrieve most relevant chunks for a query

        Args:
            query: Query text
            book_id: Optional filter by book ID
            topic_id: Optional filter by topic (will get book_id from topic)
            top_k: Number of top results to return

        Returns:
            List of tuples (chunk_text, similarity_score)
        """
        # Generate query embedding
        query_embedding = self.generate_embedding(query)

        # Build query
        if topic_id:
            topic = Topic.query.get(topic_id)
            if topic:
                book_id = topic.book_id

        # Use pgvector's cosine similarity operator <=>
        # Convert embedding list to string format for pgvector
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

        if book_id:
            results = db.session.execute(
                text("""
                    SELECT chunk_text, 1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
                    FROM document_embeddings
                    WHERE book_id = :book_id
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :top_k
                """),
                {
                    'query_embedding': embedding_str,
                    'book_id': book_id,
                    'top_k': top_k
                }
            ).fetchall()
        else:
            results = db.session.execute(
                text("""
                    SELECT chunk_text, 1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
                    FROM document_embeddings
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :top_k
                """),
                {
                    'query_embedding': embedding_str,
                    'top_k': top_k
                }
            ).fetchall()

        return [(row[0], row[1]) for row in results]

    def get_context_for_topic(self, topic_id: int, top_k: int = 5) -> str:
        """
        Get relevant context for a topic

        Args:
            topic_id: Topic ID
            top_k: Number of chunks to retrieve

        Returns:
            Combined context string
        """
        topic = Topic.query.get(topic_id)
        if not topic:
            return ""

        # Use topic name as query
        results = self.retrieve_context(
            query=topic.topic_name,
            book_id=topic.book_id,
            top_k=top_k
        )

        # Combine chunks
        context_parts = [chunk for chunk, score in results]
        return "\n\n".join(context_parts)

    def initialize_pgvector(self):
        """Initialize pgvector extension (run once on setup)"""
        try:
            db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            db.session.commit()
            print("pgvector extension initialized")
        except Exception as e:
            print(f"Error initializing pgvector: {e}")
            db.session.rollback()
