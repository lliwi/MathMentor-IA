"""
OpenAI Engine implementation
"""
import os
import json
from typing import Dict, Any
from openai import OpenAI
from app.ai_engines.base import AIEngine
from app.services.cache_service import cache_service


class OpenAIEngine(AIEngine):
    """OpenAI implementation of AI Engine"""

    def __init__(self, api_key: str = None, model: str = None, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model or os.getenv('ACTIVE_AI_MODEL', 'gpt-4')
        self.client = OpenAI(api_key=self.api_key)

    def _call_chat_completion(self, messages: list, temperature: float = 0.7) -> str:
        """Helper method to call OpenAI chat completion"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content

    @cache_service.cache_exercise(ttl=3600)  # Cache for 1 hour
    def generate_exercise(self, topic: str, context: str, difficulty: str = 'medium', course: str = None) -> Dict[str, Any]:
        """Generate a math exercise using OpenAI with caching"""

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

El ejercicio debe:
- Estar basado en el contenido del libro
- Ser claro y bien formulado
- Incluir todos los datos necesarios
- Tener una solución única y verificable"""

        messages = [
            {"role": "system", "content": "Eres un profesor de matemáticas experto en crear ejercicios didácticos."},
            {"role": "user", "content": prompt}
        ]

        response = self._call_chat_completion(messages, temperature=0.8)

        try:
            # Extract JSON from response
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()

            exercise_data = json.loads(response)
            return exercise_data
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                'content': response,
                'solution': '',
                'methodology': ''
            }

    def evaluate_submission(self, exercise: str, expected_solution: str, expected_methodology: str,
                          student_answer: str, student_methodology: str) -> Dict[str, Any]:
        """Evaluate student submission using OpenAI"""

        prompt = f"""Evalúa la solución de un estudiante de matemáticas.

EJERCICIO:
{exercise}

SOLUCIÓN ESPERADA:
{expected_solution}

METODOLOGÍA ESPERADA:
{expected_methodology}

RESPUESTA DEL ESTUDIANTE:
{student_answer}

PROCEDIMIENTO DEL ESTUDIANTE:
{student_methodology}

Evalúa lo siguiente y responde en formato JSON:
{{
    "is_correct_result": true/false,
    "is_correct_methodology": true/false,
    "errors_found": ["lista", "de", "errores"],
    "feedback": "Retroalimentación detallada"
}}

Criterios:
- is_correct_result: ¿La respuesta final es correcta?
- is_correct_methodology: ¿El procedimiento es correcto aunque haya errores de cálculo menores?
- errors_found: Lista específica de errores conceptuales o procedimentales
- feedback: Explicación didáctica breve (se generará feedback detallado después si es necesario)"""

        messages = [
            {"role": "system", "content": "Eres un profesor de matemáticas experto en evaluar trabajos de estudiantes."},
            {"role": "user", "content": prompt}
        ]

        response = self._call_chat_completion(messages, temperature=0.3)

        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()

            evaluation = json.loads(response)
            return evaluation
        except json.JSONDecodeError:
            return {
                'is_correct_result': False,
                'is_correct_methodology': False,
                'errors_found': ['Error al evaluar'],
                'feedback': response
            }

    def generate_feedback(self, exercise: str, student_answer: str, student_methodology: str,
                         errors: list, context: str = None) -> str:
        """Generate detailed feedback using OpenAI"""

        prompt = f"""Genera retroalimentación didáctica detallada para un estudiante.

EJERCICIO:
{exercise}

RESPUESTA DEL ESTUDIANTE:
{student_answer}

PROCEDIMIENTO DEL ESTUDIANTE:
{student_methodology}

ERRORES IDENTIFICADOS:
{', '.join(errors)}

Genera retroalimentación que:
1. Identifique específicamente dónde está el error
2. Explique por qué es incorrecto
3. Proporcione la forma correcta de abordarlo
4. Use un tono motivador y educativo
5. Incluya un ejemplo o pista para ayudar al estudiante

La retroalimentación debe ser clara, concisa pero completa (máximo 200 palabras)."""

        messages = [
            {"role": "system", "content": "Eres un tutor de matemáticas paciente y didáctico."},
            {"role": "user", "content": prompt}
        ]

        return self._call_chat_completion(messages, temperature=0.7)

    def generate_hint(self, exercise: str, context: str = None) -> str:
        """Generate a hint using OpenAI"""

        prompt = f"""Genera una pista útil para ayudar a resolver este ejercicio de matemáticas:

EJERCICIO:
{exercise}

La pista debe:
- Orientar sin revelar la solución completa
- Sugerir el primer paso o concepto clave
- Ser breve (máximo 50 palabras)
- Motivar al estudiante a pensar por sí mismo"""

        messages = [
            {"role": "system", "content": "Eres un tutor de matemáticas que da pistas útiles sin revelar la solución."},
            {"role": "user", "content": prompt}
        ]

        return self._call_chat_completion(messages, temperature=0.7)

    def extract_topics(self, text_chunks: list, book_metadata: Dict[str, str]) -> list:
        """Extract topics from book chunks using OpenAI"""
        import sys

        print(f"[DEBUG OpenAI] Extrayendo temas de {len(text_chunks)} chunks", flush=True)
        print(f"[DEBUG OpenAI] Metadata: {book_metadata}", flush=True)
        sys.stdout.flush()

        # Combine first 10 chunks to get table of contents or main structure
        sample_text = '\n\n'.join(text_chunks[:10])
        print(f"[DEBUG OpenAI] Longitud del texto de muestra: {len(sample_text)} caracteres", flush=True)
        print(f"[DEBUG OpenAI] Primeros 500 caracteres del texto:", flush=True)
        print(sample_text[:500], flush=True)
        sys.stdout.flush()

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

        messages = [
            {"role": "system", "content": "Eres un experto en análisis de contenido educativo."},
            {"role": "user", "content": prompt}
        ]

        print(f"[DEBUG OpenAI] Llamando a OpenAI con modelo: {self.model}", flush=True)
        sys.stdout.flush()
        response = self._call_chat_completion(messages, temperature=0.3)

        print(f"[DEBUG OpenAI] ===== RESPUESTA CRUDA DE OPENAI =====", flush=True)
        print(f"[DEBUG OpenAI] Tipo: {type(response)}", flush=True)
        print(f"[DEBUG OpenAI] Longitud: {len(response)}", flush=True)
        print(f"[DEBUG OpenAI] Contenido completo:", flush=True)
        print(response, flush=True)
        print(f"[DEBUG OpenAI] ====================================", flush=True)
        sys.stdout.flush()

        try:
            original_response = response
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
                print(f"[DEBUG OpenAI] JSON extraído de bloque markdown con ```json", flush=True)
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()
                print(f"[DEBUG OpenAI] JSON extraído de bloque markdown con ```", flush=True)

            print(f"[DEBUG OpenAI] JSON a parsear:", flush=True)
            print(response, flush=True)
            sys.stdout.flush()

            data = json.loads(response)
            print(f"[DEBUG OpenAI] JSON parseado correctamente: {data}", flush=True)

            topics = data.get('topics', [])
            print(f"[DEBUG OpenAI] Temas extraídos: {len(topics)}", flush=True)
            print(f"[DEBUG OpenAI] Lista de temas: {topics}", flush=True)
            sys.stdout.flush()

            return topics
        except json.JSONDecodeError as e:
            print(f"[DEBUG OpenAI] ERROR al parsear JSON: {str(e)}", flush=True)
            print(f"[DEBUG OpenAI] Respuesta original: {original_response}", flush=True)
            sys.stdout.flush()
            return []

    @cache_service.cache_summary(ttl=86400)  # Cache for 24 hours
    def generate_topic_summary(self, topic: str, context: str, course: str = None) -> str:
        """Generate a comprehensive topic summary using OpenAI with caching"""

        prompt = f"""Eres un profesor de matemáticas experto. Genera un resumen de estudio completo y didáctico sobre el siguiente tema:

TEMA: {topic}
CURSO: {course or 'No especificado'}

CONTENIDO DEL LIBRO DE TEXTO:
{context}

Genera un resumen bien estructurado que incluya:

1. **Conceptos Clave**: Lista los conceptos fundamentales del tema
2. **Definiciones Importantes**: Define los términos técnicos relevantes
3. **Fórmulas y Propiedades**: Enumera las fórmulas principales y propiedades matemáticas
4. **Procedimientos**: Explica paso a paso los procedimientos comunes
5. **Ejemplos Resueltos**: Incluye 1-2 ejemplos completamente resueltos
6. **Consejos y Trucos**: Añade tips útiles para recordar conceptos o evitar errores comunes
7. **Relación con Otros Temas**: Menciona cómo se relaciona con otros conceptos matemáticos

El resumen debe:
- Ser claro y didáctico
- Usar formato Markdown para una mejor presentación
- Ser comprensible para estudiantes del nivel especificado
- Tener una longitud apropiada (800-1200 palabras)
- Incluir ejemplos prácticos y visuales cuando sea posible
- Estar basado en el contenido del libro proporcionado

Formato del resumen: Markdown con secciones bien diferenciadas."""

        messages = [
            {"role": "system", "content": "Eres un profesor de matemáticas experto en crear materiales de estudio didácticos y completos."},
            {"role": "user", "content": prompt}
        ]

        return self._call_chat_completion(messages, temperature=0.7)
