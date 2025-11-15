"""
Cache Service using Redis for exercise generation and context retrieval
"""
import os
import json
import hashlib
import time
from functools import wraps
from typing import Optional, Any, Callable
import redis


class CacheService:
    """Redis-based caching service for performance optimization"""

    _instance = None
    _redis_client = None

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(CacheService, cls).__new__(cls)

            # Initialize Redis connection
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_db = int(os.getenv('REDIS_DB', 0))

            try:
                cls._redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                cls._redis_client.ping()
                print(f"[CacheService] Connected to Redis at {redis_host}:{redis_port}")
            except (redis.ConnectionError, redis.TimeoutError) as e:
                print(f"[CacheService] Warning: Redis not available ({e}). Caching disabled.")
                cls._redis_client = None

        return cls._instance

    def __init__(self):
        """Initialize cache service"""
        self.redis = self._redis_client

    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self.redis is not None

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self.is_available():
            return None

        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            print(f"[CacheService] Error getting key {key}: {e}")

        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in cache with TTL

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            self.redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            print(f"[CacheService] Error setting key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        if not self.is_available():
            return False

        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            print(f"[CacheService] Error deleting key {key}: {e}")
            return False

    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern

        Args:
            pattern: Redis key pattern (e.g., "exercise:*")

        Returns:
            Number of keys deleted
        """
        if not self.is_available():
            return 0

        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            print(f"[CacheService] Error clearing pattern {pattern}: {e}")
            return 0

    @staticmethod
    def generate_cache_key(prefix: str, **kwargs) -> str:
        """
        Generate deterministic cache key from parameters

        Args:
            prefix: Key prefix (e.g., "exercise", "context")
            **kwargs: Parameters to include in key

        Returns:
            Cache key string
        """
        # Sort kwargs for deterministic key
        sorted_params = sorted(kwargs.items())
        params_str = json.dumps(sorted_params, sort_keys=True)
        hash_value = hashlib.md5(params_str.encode()).hexdigest()
        return f"{prefix}:{hash_value}"

    def cache_exercise(self, ttl: int = 3600):
        """
        Decorator to cache exercise generation

        Args:
            ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.generate_cache_key(
                    'exercise',
                    topic=kwargs.get('topic', ''),
                    difficulty=kwargs.get('difficulty', 'medium'),
                    course=kwargs.get('course', '')
                )

                # Try cache
                start_cache_get = time.time()
                cached_value = self.get(cache_key)
                cache_get_time = time.time() - start_cache_get
                print(f"[CACHE-TIMING] Exercise Redis GET: {cache_get_time:.3f}s")

                if cached_value:
                    print(f"[CacheService] Cache HIT for exercise: {cache_key}")
                    return cached_value

                # Generate and cache
                print(f"[CacheService] Cache MISS for exercise: {cache_key}")
                start_func = time.time()
                result = func(*args, **kwargs)
                func_time = time.time() - start_func
                print(f"[CACHE-TIMING] AI generate_exercise call: {func_time:.3f}s")

                start_cache_set = time.time()
                self.set(cache_key, result, ttl)
                cache_set_time = time.time() - start_cache_set
                print(f"[CACHE-TIMING] Exercise Redis SET: {cache_set_time:.3f}s")

                return result

            return wrapper
        return decorator

    def cache_context(self, ttl: int = 7200):
        """
        Decorator to cache RAG context retrieval

        Args:
            ttl: Cache time-to-live in seconds (default: 2 hours)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                topic_id = kwargs.get('topic_id') or (args[1] if len(args) > 1 else None)
                top_k = kwargs.get('top_k', 5)

                cache_key = self.generate_cache_key(
                    'context',
                    topic_id=topic_id,
                    top_k=top_k
                )

                # Try cache
                start_cache_get = time.time()
                cached_value = self.get(cache_key)
                cache_get_time = time.time() - start_cache_get
                print(f"[CACHE-TIMING] Redis GET operation: {cache_get_time:.3f}s")

                if cached_value:
                    print(f"[CacheService] Cache HIT for context: {cache_key}")
                    return cached_value

                # Generate and cache
                print(f"[CacheService] Cache MISS for context: {cache_key}")
                start_func = time.time()
                result = func(*args, **kwargs)
                func_time = time.time() - start_func
                print(f"[CACHE-TIMING] Function execution (cache miss): {func_time:.3f}s")

                start_cache_set = time.time()
                self.set(cache_key, result, ttl)
                cache_set_time = time.time() - start_cache_set
                print(f"[CACHE-TIMING] Redis SET operation: {cache_set_time:.3f}s")

                return result

            return wrapper
        return decorator

    def cache_summary(self, ttl: int = 86400):
        """
        Decorator to cache topic summaries

        Args:
            ttl: Cache time-to-live in seconds (default: 24 hours)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key from topic
                cache_key = self.generate_cache_key(
                    'summary',
                    topic=kwargs.get('topic', ''),
                    course=kwargs.get('course', '')
                )

                # Try cache
                cached_value = self.get(cache_key)
                if cached_value:
                    print(f"[CacheService] Cache HIT for summary: {cache_key}")
                    return cached_value

                # Generate and cache
                print(f"[CacheService] Cache MISS for summary: {cache_key}")
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result

            return wrapper
        return decorator


# Singleton instance
cache_service = CacheService()
