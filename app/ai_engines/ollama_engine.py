"""
Ollama Engine implementation (for local models)
"""
import os
import json
import requests
from typing import Dict, Any
from app.ai_engines.base import AIEngine, LATEX_INSTRUCTIONS, LATEX_JSON_NOTE
from app.services.cache_service import cache_service


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

    @cache_service.cache_exercise(ttl=3600)  # Cache for 1 hour
    def generate_exercise(self, topic: str, context: str, difficulty: str = 'medium', course: str = None, source_info: Dict[str, str] = None, existing_exercises: list = None, iteration: int = None) -> Dict[str, Any]:
        """Generate exercise using Ollama with caching"""

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

        prompt = f"""Eres un profesor de matemáticas. Genera un ejercicio de matemáticas.

Tema: {topic}
Curso: {course or 'No especificado'}{source_text}
Dificultad: {difficulty}{iteration_text}{existing_text}

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
IMPORTANTE: Cada procedimiento debe tener "description" que explique qué es.
IMPORTANTE: En el enunciado, cuando el problema involucre magnitudes físicas (longitud, peso, tiempo, velocidad, área, volumen, etc.), SIEMPRE especifica claramente: "Indica las unidades en tu respuesta" o "Expresa el resultado con sus unidades correspondientes"
IMPORTANTE: Usa emoticonos apropiados para hacer el ejercicio más divertido y motivador
  Ejemplos: 📐 📏 📊 🔢 ➕ ➖ ✖️ ➗ 🎯 💡 🤔 ⭐ 🎨 📈 📉 🔺 🔻 ⚖️ 🎲
CRÍTICO: Genera un ejercicio ÚNICO y ORIGINAL. Varía la temática contextual (diferentes situaciones de la vida real, diferentes enfoques del problema). Usa valores numéricos completamente diferentes. NO repitas ejercicios similares a los ya generados.
{LATEX_INSTRUCTIONS}{LATEX_JSON_NOTE}"""

        response = self._call_generate(prompt, temperature=0.8)

        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            return json.loads(response)
        except:
            return {'content': response, 'solution': '', 'methodology': ''}

    def evaluate_submission(self, exercise: str, expected_solution: str, expected_methodology: str,
                          student_answer: str, student_methodology: str) -> Dict[str, Any]:
        """Evaluate submission using Ollama with coherent reference"""
        prompt = f"""Evalúa esta solución de matemáticas.

Ejercicio: {exercise}

SOLUCIÓN CORRECTA (REFERENCIA ÚNICA): {expected_solution}

Respuesta estudiante: {student_answer}

IMPORTANTE: La SOLUCIÓN CORRECTA es LA ÚNICA válida. NO recalcules el problema. Compara exactamente con esta solución.
IMPORTANTE: Usa emoticonos apropiados para hacer el feedback más amigable y motivador
  Ejemplos: ✅ ❌ 👍 💪 🎯 ⭐ 🤔 💡 📝 ✨ 🚀

Responde en JSON: {{"is_correct_result": true/false, "is_correct_methodology": true/false, "errors_found": [], "feedback": ""}}"""

        response = self._call_generate(prompt, temperature=0.2)

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
        """Generate feedback using Ollama with coherent reference"""
        prompt = f"""Genera retroalimentación didáctica.

Ejercicio: {exercise}

SOLUCIÓN CORRECTA (REFERENCIA ÚNICA): {expected_solution}

Respuesta: {student_answer}
Errores: {', '.join(errors)}

IMPORTANTE: Compara con la SOLUCIÓN CORRECTA únicamente. NO recalcules. Explica errores basándote en la diferencia con la solución correcta.
IMPORTANTE: Usa emoticonos apropiados para hacer el feedback más amigable y motivador
  Ejemplos: 💡 🤔 ✨ 📝 👀 ⚠️ 💪 🎯 ⭐ 🚀 ✅ 📚
{LATEX_INSTRUCTIONS}"""

        return self._call_generate(prompt, temperature=0.5)

    def generate_hint(self, exercise: str, context: str = None) -> str:
        """Generate hint using Ollama"""
        prompt = f"""Genera una pista breve para ayudar a resolver este ejercicio sin dar la solución:

EJERCICIO:
{exercise}

INSTRUCCIONES:
- Proporciona una pista orientadora, no resuelvas el problema
- Mantén la pista breve y concisa
- IMPORTANTE: Usa emoticonos apropiados para hacer la pista más amigable y motivadora
  Ejemplos: 💡 🤔 🎯 👀 ✨ 🔍 💭 🌟 📌 🔑
{LATEX_INSTRUCTIONS}"""
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

    @cache_service.cache_summary(ttl=86400)
    def generate_topic_summary(self, topic: str, context: str, course: str = None, source_info: Dict[str, str] = None) -> str:
        """Generate a comprehensive topic summary using Ollama with caching"""

        # Add source information to the prompt
        source_text = ""
        if source_info:
            if source_info.get('type') == 'book':
                source_text = f"\nFUENTE: Libro '{source_info.get('title')}' ({source_info.get('course')} - {source_info.get('subject')})"
            elif source_info.get('type') == 'video':
                source_text = f"\nFUENTE: Video '{source_info.get('title')}' del canal {source_info.get('channel')}"

        prompt = f"""Eres un profesor de matemáticas experto. Genera un resumen de estudio completo y didáctico sobre el siguiente tema:

TEMA: {topic}
CURSO: {course or "No especificado"}{source_text}

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

        return self._call_generate(prompt, temperature=0.7)

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

        response = self._call_generate(prompt, temperature=0.5)

        # Clean up response - remove markdown code blocks if present
        if '```mermaid' in response:
            response = response.split('```mermaid')[1].split('```')[0].strip()
        elif '```' in response:
            response = response.split('```')[1].split('```')[0].strip()

        return response.strip()

