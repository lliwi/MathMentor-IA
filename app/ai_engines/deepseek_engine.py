"""
DeepSeek Engine implementation
"""
import os
import json
import time
import requests
from typing import Dict, Any
from app.ai_engines.base import AIEngine, LATEX_INSTRUCTIONS, LATEX_JSON_NOTE
from app.services.cache_service import cache_service


class DeepSeekEngine(AIEngine):
    """DeepSeek implementation of AI Engine (compatible with OpenAI API)"""

    def __init__(self, api_key: str = None, model: str = None, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.model = model or 'deepseek-chat'
        self.base_url = 'https://api.deepseek.com/v1'

    def _call_chat_completion(self, messages: list, temperature: float = 0.7) -> str:
        """Helper method to call DeepSeek chat completion"""
        start_api = time.time()
        print(f"[AI-TIMING] Calling DeepSeek API with model={self.model}, temperature={temperature}")

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
            json=data,
            timeout=60  # 60 second timeout
        )
        response.raise_for_status()

        api_time = time.time() - start_api
        print(f"[AI-TIMING] DeepSeek API call completed: {api_time:.2f}s")

        start_extract = time.time()
        content = response.json()['choices'][0]['message']['content']
        extract_time = time.time() - start_extract
        print(f"[AI-TIMING] Extract response content: {extract_time:.3f}s")

        return content

    @cache_service.cache_exercise(ttl=3600)  # Cache for 1 hour
    def generate_exercise(self, topic: str, context: str, difficulty: str = 'medium', course: str = None, source_info: Dict[str, str] = None, existing_exercises: list = None, iteration: int = None) -> Dict[str, Any]:
        """Generate exercise with caching - same logic as OpenAI"""
        difficulty_map = {
            'easy': 'nivel básico, conceptos fundamentales',
            'medium': 'nivel intermedio, requiere varios pasos',
            'hard': 'nivel avanzado, requiere pensamiento crítico'
        }

        # Add source information to the prompt
        source_text = ""
        if source_info:
            if source_info.get('type') == 'book':
                source_text = f"\nFuente: Libro '{source_info.get('title')}' ({source_info.get('course')} - {source_info.get('subject')})"
            elif source_info.get('type') == 'video':
                source_text = f"\nFuente: Video '{source_info.get('title')}' del canal {source_info.get('channel')}"

        # Add information about existing exercises to avoid duplicates
        existing_text = ""
        if existing_exercises:
            existing_text = "\n\nEJERCICIOS YA GENERADOS (NO REPETIR):\n"
            for idx, ex in enumerate(existing_exercises[:5], 1):  # Show last 5 exercises
                existing_text += f"{idx}. {ex[:200]}...\n"
            existing_text += "\nIMPORTANTE: El nuevo ejercicio debe ser COMPLETAMENTE DIFERENTE de los anteriores. Cambia tanto la situación/contexto como los valores numéricos."

        iteration_text = f"\nEste es el ejercicio #{iteration} de la serie." if iteration else ""

        prompt = f"""Genera un ejercicio de matemáticas en JSON:

Tema: {topic}
Curso: {course or 'No especificado'}{source_text}
Dificultad: {difficulty_map.get(difficulty, 'medio')}
Contexto: {context[:500]}{iteration_text}{existing_text}

JSON esperado:
{{
    "content": "Enunciado del ejercicio",
    "solution": "Resultado final",
    "methodology": "Pasos de resolución",
    "available_procedures": [
        {{"id": 1, "name": "Procedimiento", "description": "Qué es"}},
        {{"id": 2, "name": "Otro", "description": "Qué es"}}
    ],
    "expected_procedures": [1, 3]
}}

Requisitos:
- 4-6 procedimientos (algunos correctos, otros no)
- Descripciones de 1 línea máximo
- Sin texto adicional fuera del JSON
- IMPORTANTE: En el enunciado, cuando el problema involucre magnitudes físicas (longitud, peso, tiempo, velocidad, área, volumen, etc.), SIEMPRE especifica claramente: "Indica las unidades en tu respuesta" o "Expresa el resultado con sus unidades correspondientes"
- IMPORTANTE: Usa emoticonos apropiados para hacer el ejercicio más divertido y motivador
  Ejemplos: 📐 📏 📊 🔢 ➕ ➖ ✖️ ➗ 🎯 💡 🤔 ⭐ 🎨 📈 📉 🔺 🔻 ⚖️ 🎲
- CRÍTICO: Genera un ejercicio ÚNICO y ORIGINAL. Varía la temática contextual (diferentes situaciones de la vida real, diferentes enfoques del problema). Usa valores numéricos completamente diferentes. NO repitas ejercicios similares a los ya generados.
{LATEX_INSTRUCTIONS}{LATEX_JSON_NOTE}"""

        messages = [
            {"role": "system", "content": "Eres un profesor de matemáticas experto. Usa emoticonos para hacer el contenido más visual y atractivo."},
            {"role": "user", "content": prompt}
        ]

        response = self._call_chat_completion(messages, temperature=0.5)

        start_parse = time.time()
        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            exercise_data = json.loads(response)
            parse_time = time.time() - start_parse
            print(f"[AI-TIMING] JSON parsing: {parse_time:.3f}s")
            return exercise_data
        except:
            return {'content': response, 'solution': '', 'methodology': ''}

    def evaluate_submission(self, exercise: str, expected_solution: str, expected_methodology: str,
                          student_answer: str, student_methodology: str) -> Dict[str, Any]:
        """Evaluate submission with coherent reference"""
        prompt = f"""Evalúa la solución de un estudiante.

EJERCICIO: {exercise}

SOLUCIÓN CORRECTA (REFERENCIA ÚNICA): {expected_solution}

RESPUESTA ESTUDIANTE: {student_answer}

INSTRUCCIONES CRÍTICAS:
- La "SOLUCIÓN CORRECTA" es LA ÚNICA respuesta válida
- NO recalcules el problema
- Compara la respuesta del estudiante con esta solución EXACTAMENTE
- IMPORTANTE: Usa emoticonos apropiados para hacer el feedback más amigable y motivador
  Ejemplos: ✅ ❌ 👍 💪 🎯 ⭐ 🤔 💡 📝 ✨ 🚀

Responde en JSON: {{"is_correct_result": bool, "is_correct_methodology": bool, "errors_found": [], "feedback": ""}}"""

        messages = [
            {"role": "system", "content": "Eres un profesor evaluador. IMPORTANTE: Usa SIEMPRE la solución proporcionada como referencia única. Usa emoticonos para hacer el feedback más amigable."},
            {"role": "user", "content": prompt}
        ]

        response = self._call_chat_completion(messages, temperature=0.2)

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

    def generate_feedback(self, exercise: str, expected_solution: str, student_answer: str,
                         student_methodology: str, errors: list, context: str = None) -> str:
        """Generate feedback with coherent reference"""
        prompt = f"""Genera retroalimentación didáctica.

EJERCICIO: {exercise}

SOLUCIÓN CORRECTA (REFERENCIA ÚNICA): {expected_solution}

RESPUESTA ESTUDIANTE: {student_answer}

ERRORES: {', '.join(errors)}

INSTRUCCIONES:
- Compara con la SOLUCIÓN CORRECTA únicamente
- NO recalcules el problema
- Explica los errores basándote en la diferencia con la solución correcta
- IMPORTANTE: Usa emoticonos apropiados para hacer el feedback más amigable y motivador
  Ejemplos: 💡 🤔 ✨ 📝 👀 ⚠️ 💪 🎯 ⭐ 🚀 ✅ 📚
{LATEX_INSTRUCTIONS}"""

        messages = [
            {"role": "system", "content": "Eres un tutor paciente. IMPORTANTE: Usa la solución proporcionada como referencia única. Usa emoticonos para hacer el feedback más visual y motivador."},
            {"role": "user", "content": prompt}
        ]

        return self._call_chat_completion(messages, temperature=0.5)

    def generate_hint(self, exercise: str, context: str = None) -> str:
        """Generate hint"""
        prompt = f"""Genera una pista breve para ayudar a resolver este ejercicio sin dar la solución:

EJERCICIO:
{exercise}

INSTRUCCIONES:
- Proporciona una pista orientadora, no resuelvas el problema
- Mantén la pista breve y concisa
- IMPORTANTE: Usa emoticonos apropiados para hacer la pista más amigable y motivadora
  Ejemplos: 💡 🤔 🎯 👀 ✨ 🔍 💭 🌟 📌 🔑
{LATEX_INSTRUCTIONS}"""
        messages = [
            {"role": "system", "content": "Eres un tutor que da pistas útiles. Usa emoticonos para hacer las pistas más visuales y motivadoras."},
            {"role": "user", "content": prompt}
        ]
        return self._call_chat_completion(messages, temperature=0.7)

    def extract_topics(self, text_chunks: list, book_metadata: Dict[str, str]) -> list:
        """Extract topics from book chunks using DeepSeek"""
        import sys

        print(f"[DEBUG DeepSeek] Extrayendo temas de {len(text_chunks)} chunks", flush=True)
        print(f"[DEBUG DeepSeek] Metadata: {book_metadata}", flush=True)
        sys.stdout.flush()

        # Combine first 10 chunks to get table of contents or main structure
        sample_text = '\n\n'.join(text_chunks[:10])
        print(f"[DEBUG DeepSeek] Longitud del texto de muestra: {len(sample_text)} caracteres", flush=True)
        print(f"[DEBUG DeepSeek] Primeros 500 caracteres del texto:", flush=True)
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

    @cache_service.cache_summary(ttl=86400)
    def generate_topic_summary(self, topic: str, context: str, course: str = None, source_info: Dict[str, str] = None) -> str:
        """Generate a comprehensive topic summary using DeepSeek with caching"""

        # Add source information to the prompt
        source_text = ""
        if source_info:
            if source_info.get('type') == 'book':
                source_text = f"\nFUENTE: Libro '{source_info.get('title')}' ({source_info.get('course')} - {source_info.get('subject')})"
            elif source_info.get('type') == 'video':
                source_text = f"\nFUENTE: Video '{source_info.get('title')}' del canal {source_info.get('channel')}"

        prompt = f"""Eres un profesor de matemáticas experto. Genera un resumen de estudio completo y didáctico sobre el siguiente tema:

TEMA: {topic}
CURSO: {course or 'No especificado'}{source_text}

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
- IMPORTANTE: Usa emoticonos apropiados para hacer el resumen más visual, amigable y motivador
  Ejemplos: 📐 📏 📊 🔢 ➕ ➖ ✖️ ➗ 🎯 💡 🤔 ⭐ 📝 ✨ 🚀 📚 🔍 💭 ⚡ 🎨 📈 📉 🔺 🔻 ⚖️ 🎲 ✅ ⚠️ 💪 👀 🌟 📌 🔑
{LATEX_INSTRUCTIONS}

Formato del resumen: Markdown con secciones bien diferenciadas."""

        messages = [
            {"role": "system", "content": "Eres un profesor de matemáticas experto en crear materiales de estudio didácticos y completos. Usa emoticonos para hacer el contenido más visual y atractivo."},
            {"role": "user", "content": prompt}
        ]

        return self._call_chat_completion(messages, temperature=0.7)

    def generate_visual_scheme(self, exercise: str, context: str = None) -> str:
        """Generate a visual scheme using Mermaid diagram syntax"""

        prompt = f"""Genera un esquema visual usando sintaxis Mermaid para ayudar a resolver este ejercicio de matemáticas:

EJERCICIO:
{exercise}

Crea un diagrama Mermaid que:
- Represente visualmente la estructura del problema
- Muestre las relaciones entre los datos conocidos y desconocidos
- Sugiera el flujo lógico de resolución SIN resolverlo
- Use SOLO graph TD (NO uses flowchart ni subgraphs)

REGLAS IMPORTANTES:
- NO incluyas cálculos específicos ni resultados numéricos
- NO resuelvas el problema, solo muestra el camino
- Usa placeholders genéricos como "Calcular X", "Aplicar fórmula Y"
- El estudiante debe poder usar el diagrama para pensar por sí mismo
- Mantén el diagrama orientativo, no resolutivo

RESTRICCIONES TÉCNICAS (MUY IMPORTANTE):
- NO uses subgraph (causa errores de renderizado)
- NO uses saltos de línea dentro de los nodos
- Usa solo texto corto por nodo (máximo 40 caracteres)
- Identifica nodos con letras simples (A, B, C, D, E, etc.)
- NO uses identificadores complejos
- Máximo 8 nodos en el diagrama
- Solo usa flechas simples: -->

FORMATO:
- Devuelve SOLO el código Mermaid, sin explicaciones adicionales
- No incluyas bloques de código markdown (```mermaid)
- Empieza con: graph TD
- Usa etiquetas claras y concisas en español

Ejemplo de formato CORRECTO:
graph TD
    A[Datos del problema] --> B[Identificar incógnita]
    B --> C[Aplicar fórmula]
    C --> D[Calcular resultado]
    D --> E[Verificar coherencia]"""

        messages = [
            {"role": "system", "content": "Eres un experto en visualización de problemas matemáticos que crea diagramas Mermaid claros y didácticos."},
            {"role": "user", "content": prompt}
        ]

        response = self._call_chat_completion(messages, temperature=0.5)

        # Clean up response - remove markdown code blocks if present
        if '```mermaid' in response:
            response = response.split('```mermaid')[1].split('```')[0].strip()
        elif '```' in response:
            response = response.split('```')[1].split('```')[0].strip()

        return response.strip()
