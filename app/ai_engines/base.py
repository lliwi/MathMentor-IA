"""
Base class for AI Engines
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class AIEngine(ABC):
    """Abstract base class for AI engines"""

    def __init__(self, api_key: str = None, model: str = None, **kwargs):
        """
        Initialize AI Engine

        Args:
            api_key: API key for the service (if required)
            model: Model name/identifier
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self.model = model
        self.config = kwargs

    @abstractmethod
    def generate_exercise(self, topic: str, context: str, difficulty: str = 'medium', course: str = None) -> Dict[str, Any]:
        """
        Generate a math exercise based on topic and context

        Args:
            topic: The topic name
            context: RAG-retrieved context from textbook
            difficulty: Difficulty level (easy, medium, hard)
            course: Course level (e.g., "1º ESO")

        Returns:
            Dict with 'content', 'solution', 'methodology' keys
        """
        pass

    @abstractmethod
    def evaluate_submission(self, exercise: str, expected_solution: str, expected_methodology: str,
                          student_answer: str, student_methodology: str) -> Dict[str, Any]:
        """
        Evaluate a student's submission

        Args:
            exercise: The exercise content
            expected_solution: Expected correct answer
            expected_methodology: Expected solution steps
            student_answer: Student's answer
            student_methodology: Student's work/steps

        Returns:
            Dict with evaluation results including:
            - is_correct_result: bool
            - is_correct_methodology: bool
            - feedback: str
            - errors_found: list
        """
        pass

    @abstractmethod
    def generate_feedback(self, exercise: str, student_answer: str, student_methodology: str,
                         errors: list, context: str = None) -> str:
        """
        Generate detailed didactic feedback for student

        Args:
            exercise: The exercise content
            student_answer: Student's answer
            student_methodology: Student's work
            errors: List of identified errors
            context: Optional context from RAG

        Returns:
            Detailed feedback string
        """
        pass

    @abstractmethod
    def generate_hint(self, exercise: str, context: str = None) -> str:
        """
        Generate a hint for the exercise (to be purchased with points)

        Args:
            exercise: The exercise content
            context: Optional context from RAG

        Returns:
            Hint string
        """
        pass

    @abstractmethod
    def extract_topics(self, text_chunks: list, book_metadata: Dict[str, str]) -> list:
        """
        Extract topics from book text chunks

        Args:
            text_chunks: List of text chunks from the book
            book_metadata: Dict with 'course', 'subject', 'title'

        Returns:
            List of topic names
        """
        pass

    @abstractmethod
    def generate_topic_summary(self, topic: str, context: str, course: str = None) -> str:
        """
        Generate a comprehensive summary of a topic for study

        Args:
            topic: The topic name
            context: RAG-retrieved context from textbook
            course: Course level (e.g., "1º ESO")

        Returns:
            Formatted summary string with key concepts, formulas, and examples
        """
        pass

    @abstractmethod
    def generate_visual_scheme(self, exercise: str, context: str = None) -> str:
        """
        Generate a visual scheme/diagram for the exercise using Mermaid syntax

        Args:
            exercise: The exercise content
            context: Optional context from RAG

        Returns:
            Mermaid diagram code string
        """
        pass
