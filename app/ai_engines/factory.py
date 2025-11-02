"""
Factory for creating AI Engine instances
"""
import os
from app.ai_engines.base import AIEngine
from app.ai_engines.openai_engine import OpenAIEngine
from app.ai_engines.deepseek_engine import DeepSeekEngine
from app.ai_engines.ollama_engine import OllamaEngine


class AIEngineFactory:
    """Factory for creating AI Engine instances"""

    _engines = {
        'openai': OpenAIEngine,
        'deepseek': DeepSeekEngine,
        'ollama': OllamaEngine
    }

    @classmethod
    def create(cls, engine_name: str = None, **kwargs) -> AIEngine:
        """
        Create an AI Engine instance

        Args:
            engine_name: Name of the engine ('openai', 'deepseek', 'ollama')
                        If None, uses ACTIVE_AI_ENGINE from environment
            **kwargs: Additional configuration for the engine

        Returns:
            AIEngine instance

        Raises:
            ValueError: If engine_name is not supported
        """
        if engine_name is None:
            engine_name = os.getenv('ACTIVE_AI_ENGINE', 'openai')

        engine_name = engine_name.lower()

        if engine_name not in cls._engines:
            raise ValueError(
                f"Engine '{engine_name}' not supported. "
                f"Available engines: {', '.join(cls._engines.keys())}"
            )

        engine_class = cls._engines[engine_name]
        return engine_class(**kwargs)

    @classmethod
    def get_available_engines(cls) -> list:
        """Get list of available engine names"""
        return list(cls._engines.keys())
