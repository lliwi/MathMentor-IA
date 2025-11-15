"""
RAG (Retrieval-Augmented Generation) Service
"""
import os
import hashlib
import numpy as np
import time
import threading
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from cachetools import LRUCache
from app import db
from app.models.document_embedding import DocumentEmbedding
from app.models.book import Book
from app.models.topic import Topic
from app.services.cache_service import cache_service


class RAGService:
    """Service for RAG operations (embedding and retrieval) - Singleton pattern"""

    _instance = None
    _model = None
    _embedding_cache = None
    _model_name = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        """Singleton pattern - only one instance of RAG service with thread safety"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RAGService, cls).__new__(cls)
            return cls._instance

    def __init__(self, model_name: str = None):
        """
        Initialize RAG Service (Singleton - model only loaded once)

        Args:
            model_name: Name of the sentence-transformer model (ignored after first init)
        """
        # Thread-safe initialization
        with self._lock:
            if not self._initialized:
                self._model_name = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
                print(f"[RAGService] Initializing singleton with model: {self._model_name}")
                try:
                    self._model = SentenceTransformer(self._model_name)
                    self._embedding_cache = LRUCache(maxsize=5000)
                    self._initialized = True
                    print(f"[RAGService] Model loaded successfully, embedding dimension: {self._model.get_sentence_embedding_dimension()}")
                except Exception as e:
                    print(f"[RAGService] Error loading model: {e}")
                    raise

        # Set instance attributes
        self.model_name = self._model_name
        self.model = self._model
        self.embedding_dim = self._model.get_sentence_embedding_dimension() if self._model else None
        self.embedding_cache = self._embedding_cache

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text with caching

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        # Generate cache key
        cache_key = hashlib.md5(text.encode()).hexdigest()

        # Check cache
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]

        # Generate embedding
        embedding = self.model.encode(text)
        embedding_list = embedding.tolist()

        # Store in cache
        self.embedding_cache[cache_key] = embedding_list

        return embedding_list

    def store_chunks(self, book_id: int, chunks: List[Dict[str, any]], batch_size: int = 32) -> int:
        """
        Generate embeddings and store chunks in database using batch processing

        Args:
            book_id: ID of the book
            chunks: List of chunk dicts from PDFProcessor
            batch_size: Number of embeddings to generate at once (default: 32)

        Returns:
            Number of chunks stored
        """
        stored_count = 0

        # Process chunks in batches for better performance
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            texts = [chunk['text'] for chunk in batch]

            # Batch encoding (much faster than one-by-one)
            print(f"[RAGService] Processing batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1} ({len(batch)} chunks)")
            embeddings = self.model.encode(texts, batch_size=batch_size, show_progress_bar=False)

            # Store in database
            for chunk, embedding in zip(batch, embeddings):
                doc_embedding = DocumentEmbedding(
                    book_id=book_id,
                    chunk_text=chunk['text'],
                    chunk_index=chunk['chunk_index'],
                    page_number=chunk['page_number'],
                    embedding=embedding.tolist()
                )
                db.session.add(doc_embedding)
                stored_count += 1

            # Commit each batch to avoid memory issues
            db.session.commit()
            print(f"[RAGService] Batch committed ({stored_count} chunks processed)")

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
        start_embed = time.time()
        query_embedding = self.generate_embedding(query)
        embed_time = time.time() - start_embed
        print(f"[RAG-TIMING] Generate embedding: {embed_time:.3f}s")

        # Build query
        if topic_id:
            start_topic = time.time()
            topic = Topic.query.get(topic_id)
            if topic:
                book_id = topic.book_id
            topic_time = time.time() - start_topic
            print(f"[RAG-TIMING] Get topic from DB: {topic_time:.3f}s")

        # Use pgvector's cosine similarity operator <=>
        # Convert embedding list to string format for pgvector
        start_convert = time.time()
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        convert_time = time.time() - start_convert
        print(f"[RAG-TIMING] Convert embedding to string: {convert_time:.3f}s")

        if book_id:
            start_sql = time.time()
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
            sql_time = time.time() - start_sql
            print(f"[RAG-TIMING] Vector similarity SQL query: {sql_time:.3f}s")
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

    @cache_service.cache_context(ttl=86400)  # Cache for 24 hours
    def get_context_for_topic(self, topic_id: int, top_k: int = 5) -> str:
        """
        Get relevant context for a topic with caching

        Args:
            topic_id: Topic ID
            top_k: Number of chunks to retrieve

        Returns:
            Combined context string
        """
        start_total = time.time()
        print(f"[RAG-TIMING] get_context_for_topic called for topic_id={topic_id}, top_k={top_k}")

        start_topic_query = time.time()
        topic = Topic.query.get(topic_id)
        topic_query_time = time.time() - start_topic_query
        print(f"[RAG-TIMING] Topic.query.get: {topic_query_time:.3f}s")

        if not topic:
            return ""

        # Use topic name as query
        start_retrieve = time.time()
        results = self.retrieve_context(
            query=topic.topic_name,
            book_id=topic.book_id,
            top_k=top_k
        )
        retrieve_time = time.time() - start_retrieve
        print(f"[RAG-TIMING] retrieve_context call: {retrieve_time:.3f}s")

        # Combine chunks
        start_combine = time.time()
        context_parts = [chunk for chunk, score in results]
        combined = "\n\n".join(context_parts)
        combine_time = time.time() - start_combine
        print(f"[RAG-TIMING] Combine chunks: {combine_time:.3f}s")

        total_time = time.time() - start_total
        print(f"[RAG-TIMING] TOTAL get_context_for_topic: {total_time:.3f}s")

        return combined

    def initialize_pgvector(self):
        """Initialize pgvector extension (run once on setup)"""
        try:
            db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            db.session.commit()
            print("pgvector extension initialized")
        except Exception as e:
            print(f"Error initializing pgvector: {e}")
            db.session.rollback()
