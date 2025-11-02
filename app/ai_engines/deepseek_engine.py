"""
DeepSeek Engine implementation
"""
import os
import json
import requests
from typing import Dict, Any
from app.ai_engines.base import AIEngine


class DeepSeekEngine(AIEngine):
    """DeepSeek implementation of AI Engine (compatible with OpenAI API)"""

    def __init__(self, api_key: str = None, model: str = None, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.model = model or 'deepseek-chat'
        self.base_url = 'https://api.deepseek.com/v1'

    def _call_chat_completion(self, messages: list, temperature: float = 0.7) -> str:
        """Helper method to call DeepSeek chat completion"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature
        }

        response = requests.post(
            f'{self.base_url}/chat/completions',
            headers=headers,
            json=data
        )
        response.raise_for_status()

        return response.json()['choices'][0]['message']['content']

    def generate_exercise(self, topic: str, context: str, difficulty: str = 'medium', course: str = None) -> Dict[str, Any]:
        """Generate exercise - same logic as OpenAI"""
        difficulty_map = {
            'easy': 'nivel básico, conceptos fundamentales',
            'medium': 'nivel intermedio, requiere varios pasos',
            'hard': 'nivel avanzado, requiere pensamiento crítico'
        }

        prompt = f"""Eres un profesor de matemáticas experto. Genera UN ejercicio de matemáticas con las siguientes características:

Tema: {topic}
Curso: {course or 'No especificado'}
Dificultad: {difficulty_map.get(difficulty, 'medio')}

Contexto del libro de texto:
{context}

Genera el ejercicio en formato JSON con esta estructura exacta:
{{
    "content": "Enunciado completo del ejercicio",
    "solution": "Respuesta correcta (solo el resultado final)",
    "methodology": "Pasos detallados para resolver el ejercicio",
    "available_procedures": [
        {{"id": 1, "name": "Nombre del procedimiento/técnica/propiedad", "description": "Breve explicación de qué es y cuándo se usa"}},
        {{"id": 2, "name": "Otro procedimiento", "description": "Breve explicación"}},
        ...
    ],
    "expected_procedures": [1, 3, 5]
}}

IMPORTANTE sobre los procedimientos:
- available_procedures: Lista TODAS las técnicas, propiedades, reglas o procedimientos matemáticos relacionados con el ejercicio (tanto correctos como incorrectos)
- expected_procedures: IDs de los procedimientos que son necesarios para resolver correctamente el ejercicio
- Incluye al menos 6-10 procedimientos disponibles (algunos correctos, algunos incorrectos o no aplicables)
- Los procedimientos deben ser específicos (ej: "Propiedad distributiva", "Teorema de Pitágoras", "Factorización por diferencia de cuadrados")
- IMPORTANTE: Cada procedimiento DEBE incluir una "description" breve (1-2 líneas) que explique qué es y cuándo se usa
- Incluye emoticonos para hacer el ejercicio más atractivo
- No propongas acciones al final de las respuestas o pistas, el estudiante no puede interactuar con tus respuestas."""

        messages = [
            {"role": "system", "content": "Eres un profesor de matemáticas experto."},
            {"role": "user", "content": prompt}
        ]

        response = self._call_chat_completion(messages, temperature=0.8)

        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            exercise_data = json.loads(response)
            return exercise_data
        except:
            return {'content': response, 'solution': '', 'methodology': ''}

    def evaluate_submission(self, exercise: str, expected_solution: str, expected_methodology: str,
                          student_answer: str, student_methodology: str) -> Dict[str, Any]:
        """Evaluate submission - same logic as OpenAI"""
        # Implementation similar to OpenAI
        prompt = f"""Evalúa la solución de un estudiante. EJERCICIO: {exercise}
SOLUCIÓN ESPERADA: {expected_solution}
RESPUESTA ESTUDIANTE: {student_answer}

Responde en JSON: {{"is_correct_result": bool, "is_correct_methodology": bool, "errors_found": [], "feedback": ""}}"""

        messages = [
            {"role": "system", "content": "Eres un profesor evaluador."},
            {"role": "user", "content": prompt}
        ]

        response = self._call_chat_completion(messages, temperature=0.3)

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
        """Generate feedback"""
        prompt = f"""Genera retroalimentación didáctica para: EJERCICIO: {exercise}
RESPUESTA: {student_answer}
ERRORES: {', '.join(errors)}"""

        messages = [
            {"role": "system", "content": "Eres un tutor paciente."},
            {"role": "user", "content": prompt}
        ]

        return self._call_chat_completion(messages, temperature=0.7)

    def generate_hint(self, exercise: str, context: str = None) -> str:
        """Generate hint"""
        prompt = f"Genera una pista breve para: {exercise}"
        messages = [
            {"role": "system", "content": "Eres un tutor que da pistas."},
            {"role": "user", "content": prompt}
        ]
        return self._call_chat_completion(messages, temperature=0.7)

    def extract_topics(self, text_chunks: list, book_metadata: Dict[str, str]) -> list:
        """Extract topics from book chunks using DeepSeek"""
        import sys

        print(f"[DEBUG DeepSeek] Extrayendo temas de {len(text_chunks)} chunks", flush=True)
        print(f"[DEBUG DeepSeek] Metadata: {book_metadata}", flush=True)
        sys.stdout.flush()

        # Combine first few chunks to get table of contents or main structure
        sample_text = '\n\n'.join(text_chunks[:5])
        print(f"[DEBUG DeepSeek] Longitud del texto de muestra: {len(sample_text)} caracteres", flush=True)
        print(f"[DEBUG DeepSeek] Primeros 500 caracteres del texto:", flush=True)
        print(sample_text[:500], flush=True)
        sys.stdout.flush()

        prompt = f"""Analiza este texto de un libro de matemáticas y extrae los TEMAS principales.

LIBRO: {book_metadata.get('title', 'Sin título')}
CURSO: {book_metadata.get('course', 'No especificado')}
MATERIA: {book_metadata.get('subject', 'Matemáticas')}

TEXTO:
{sample_text[:3000]}

Extrae los temas principales en formato JSON:
{{
    "topics": [
        {{"name": "Nombre del tema", "description": "Breve descripción"}},
        ...
    ]
}}

Busca especialmente en el índice o tabla de contenidos si está presente."""

        messages = [
            {"role": "system", "content": "Eres un experto en análisis de contenido educativo."},
            {"role": "user", "content": prompt}
        ]

        print(f"[DEBUG DeepSeek] Llamando a DeepSeek con modelo: {self.model}", flush=True)
        sys.stdout.flush()

        try:
            response = self._call_chat_completion(messages, temperature=0.3)

            print(f"[DEBUG DeepSeek] ===== RESPUESTA CRUDA DE DEEPSEEK =====", flush=True)
            print(f"[DEBUG DeepSeek] Tipo: {type(response)}", flush=True)
            print(f"[DEBUG DeepSeek] Longitud: {len(response)}", flush=True)
            print(f"[DEBUG DeepSeek] Contenido completo:", flush=True)
            print(response, flush=True)
            print(f"[DEBUG DeepSeek] ====================================", flush=True)
            sys.stdout.flush()

            original_response = response
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
                print(f"[DEBUG DeepSeek] JSON extraído de bloque markdown con ```json", flush=True)
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()
                print(f"[DEBUG DeepSeek] JSON extraído de bloque markdown con ```", flush=True)

            print(f"[DEBUG DeepSeek] JSON a parsear:", flush=True)
            print(response, flush=True)
            sys.stdout.flush()

            data = json.loads(response)
            print(f"[DEBUG DeepSeek] JSON parseado correctamente: {data}", flush=True)

            topics = data.get('topics', [])
            print(f"[DEBUG DeepSeek] Temas extraídos: {len(topics)}", flush=True)
            print(f"[DEBUG DeepSeek] Lista de temas: {topics}", flush=True)
            sys.stdout.flush()

            return topics
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG DeepSeek] ERROR en la petición HTTP: {str(e)}", flush=True)
            sys.stdout.flush()
            return []
        except json.JSONDecodeError as e:
            print(f"[DEBUG DeepSeek] ERROR al parsear JSON: {str(e)}", flush=True)
            print(f"[DEBUG DeepSeek] Respuesta original: {original_response if 'original_response' in locals() else 'N/A'}", flush=True)
            sys.stdout.flush()
            return []
        except Exception as e:
            print(f"[DEBUG DeepSeek] ERROR inesperado: {type(e).__name__}: {str(e)}", flush=True)
            sys.stdout.flush()
            return []
