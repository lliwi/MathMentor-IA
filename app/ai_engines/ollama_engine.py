"""
Ollama Engine implementation (for local models)
"""
import os
import json
import requests
from typing import Dict, Any
from app.ai_engines.base import AIEngine


class OllamaEngine(AIEngine):
    """Ollama implementation for local LLM models"""

    def __init__(self, api_key: str = None, model: str = None, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = model or 'llama2'

    def _call_generate(self, prompt: str, temperature: float = 0.7) -> str:
        """Helper method to call Ollama generate endpoint"""
        response = requests.post(
            f'{self.base_url}/api/generate',
            json={
                'model': self.model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': temperature
                }
            }
        )
        response.raise_for_status()
        return response.json()['response']

    def generate_exercise(self, topic: str, context: str, difficulty: str = 'medium', course: str = None) -> Dict[str, Any]:
        """Generate exercise using Ollama"""
        prompt = f"""Eres un profesor de matemáticas. Genera un ejercicio de matemáticas.

Tema: {topic}
Curso: {course or 'No especificado'}
Dificultad: {difficulty}

Contexto:
{context[:1000]}

Responde en formato JSON:
{{
    "content": "ejercicio",
    "solution": "solución",
    "methodology": "pasos",
    "available_procedures": [
        {{"id": 1, "name": "Propiedad/técnica 1", "description": "Breve explicación"}},
        {{"id": 2, "name": "Propiedad/técnica 2", "description": "Breve explicación"}}
    ],
    "expected_procedures": [1, 3]
}}

Incluye 6-10 procedimientos matemáticos (algunos correctos, otros no aplicables).
IMPORTANTE: Cada procedimiento debe tener "description" que explique qué es."""

        response = self._call_generate(prompt, temperature=0.8)

        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            return json.loads(response)
        except:
            return {'content': response, 'solution': '', 'methodology': ''}

    def evaluate_submission(self, exercise: str, expected_solution: str, expected_methodology: str,
                          student_answer: str, student_methodology: str) -> Dict[str, Any]:
        """Evaluate submission using Ollama"""
        prompt = f"""Evalúa esta solución de matemáticas.
Ejercicio: {exercise}
Respuesta esperada: {expected_solution}
Respuesta estudiante: {student_answer}

Responde en JSON: {{"is_correct_result": true/false, "is_correct_methodology": true/false, "errors_found": [], "feedback": ""}}"""

        response = self._call_generate(prompt, temperature=0.3)

        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            return json.loads(response)
        except:
            return {
                'is_correct_result': False,
                'is_correct_methodology': False,
                'errors_found': [],
                'feedback': response
            }

    def generate_feedback(self, exercise: str, student_answer: str, student_methodology: str,
                         errors: list, context: str = None) -> str:
        """Generate feedback using Ollama"""
        prompt = f"""Genera retroalimentación didáctica.
Ejercicio: {exercise}
Respuesta: {student_answer}
Errores: {', '.join(errors)}

Explica los errores de forma educativa."""

        return self._call_generate(prompt, temperature=0.7)

    def generate_hint(self, exercise: str, context: str = None) -> str:
        """Generate hint using Ollama"""
        prompt = f"Genera una pista breve sin revelar la solución: {exercise}"
        return self._call_generate(prompt, temperature=0.7)

    def extract_topics(self, text_chunks: list, book_metadata: Dict[str, str]) -> list:
        """Extract topics using Ollama"""
        sample_text = '\n\n'.join(text_chunks[:10])

        prompt = f"""Extrae los temas y subtemas de este libro de matemáticas en formato JSON.

LIBRO: {book_metadata.get('title', 'Sin título')}
CURSO: {book_metadata.get('course', 'No especificado')}
MATERIA: {book_metadata.get('subject', 'Matemáticas')}

TEXTO:
{sample_text}

Formato de respuesta esperado:
{{
    "topics": [
        {{"name": "Nombre del tema", "description": "Breve descripción"}},
        ...
    ]
}}

Busca especialmente en el índice o tabla de contenidos si está presente."""

        response = self._call_generate(prompt, temperature=0.3)

        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            data = json.loads(response)
            return data.get('topics', [])
        except:
            return []
