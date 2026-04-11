# MathMentor IA

**MathMentor IA** es una aplicación educativa de vanguardia que utiliza Inteligencia Artificial para transformar el aprendizaje de matemáticas mediante práctica personalizada, corrección inteligente y gamificación.

## Características Principales

- **Generación de Ejercicios Personalizados** con IA basada en libros de texto específicos
- **Selección de Procedimientos/Técnicas** mediante checkboxes en lugar de texto libre para mejor evaluación
- **Corrección Inteligente con Feedback Didáctico** que analiza tanto el resultado como el procedimiento
- **Sistema de Puntuación y Gamificación** para motivar el aprendizaje continuo
- **RAG (Retrieval-Augmented Generation)** para contextualizar ejercicios con el material de estudio
- **Múltiples Motores de IA** soportados: OpenAI, DeepSeek, Ollama

## Stack Tecnológico

- **Backend:** Flask (Python)
- **Base de Datos:** PostgreSQL con pgvector
- **IA:** OpenAI, DeepSeek, Ollama
- **Containerización:** Docker Compose
- **Frontend:** Bootstrap 5 + JavaScript

## Instalación y Configuración

### Requisitos Previos

- Docker y Docker Compose
- Python 3.11+ (para desarrollo local sin Docker)
- Cuenta de OpenAI o DeepSeek (opcional, para funcionalidad IA)

### Configuración Rápida con Docker

1. **Clonar el repositorio:**
```bash
git clone <repository-url>
cd "MathMentor IA"
```

2. **Configurar variables de entorno:**
```bash
cp .env.example .env
```

Edita el archivo `.env` y configura:
- `SECRET_KEY`: Clave secreta para Flask
- `OPENAI_API_KEY`: Tu clave API de OpenAI (si usas OpenAI)
- `DEEPSEEK_API_KEY`: Tu clave API de DeepSeek (si usas DeepSeek)
- `ACTIVE_AI_ENGINE`: Motor activo (openai, deepseek, ollama)

3. **Iniciar la aplicación:**
```bash
docker-compose up -d
```

4. **Aplicar índices de performance (RECOMENDADO):**
```bash
# Esperar a que los servicios estén listos (30 segundos)
docker-compose exec web python add_indexes.py
```

Este paso es **altamente recomendado** para optimizar la performance de búsquedas vectoriales y generación de ejercicios.

5. **Acceder a la aplicación:**
- Abrir navegador en: http://localhost:5000

### 🚀 Performance Optimizations

La aplicación incluye múltiples optimizaciones de performance:
- **Redis Cache**: Caché de ejercicios y contextos RAG (70-90% reducción de latencia)
- **Cache Prefetching**: Precarga automática de contextos al acceder a `/student/practice`
- **Connection Pooling**: Pool de conexiones PostgreSQL optimizado
- **Batch Processing**: Procesamiento paralelo de embeddings (3-5x más rápido)
- **Singleton Pattern**: Carga única del modelo de embeddings
- **HNSW Indexes**: Índices vectoriales optimizados para búsquedas

Ver [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md) para detalles completos y [CACHE_PREFETCHING.md](CACHE_PREFETCHING.md) para la funcionalidad de precarga.

## Integración con YouTube (Importación y Transcripción de Vídeos)

MathMentor IA permite importar vídeos de YouTube como material de estudio. El sistema extrae la transcripción del vídeo (si existe) o la genera automáticamente mediante Whisper cuando no está disponible.

### Estrategia de Extracción de Transcripciones

El servicio [app/services/youtube_service.py](app/services/youtube_service.py) implementa una cadena de *fallbacks* para maximizar el índice de éxito:

1. **`youtube-transcript-api`** — Intenta obtener la transcripción oficial publicada por el creador del vídeo.
2. **`pytubefix` (subtítulos)** — Si la API oficial falla, intenta extraer los subtítulos mediante pytubefix.
3. **`yt-dlp` (subtítulos)** — Si los dos métodos anteriores fallan, usa yt-dlp para intentar obtener subtítulos manuales o auto-generados.
4. **Whisper (último recurso)** — Si no existe ninguna transcripción, descarga el audio del vídeo y lo transcribe localmente o vía API.

Cada método está aislado en su propio `try/except`, de modo que un fallo en uno no impide que los siguientes se ejecuten. Whisper siempre se invoca como último recurso si todos los anteriores fracasan.

### Proveedores de Whisper Soportados

El método `_detect_whisper_provider()` auto-detecta el proveedor disponible en el siguiente orden:

| Proveedor | Configuración | Notas |
|-----------|---------------|-------|
| **Groq API** | `GROQ_API_KEY` en `.env` | Más rápido y económico. Usa `whisper-large-v3`. |
| **OpenAI API** | `OPENAI_API_KEY` en `.env` | Alta calidad. Usa `whisper-1`. |
| **Local (faster-whisper)** | Sin claves API | Ejecuta Whisper en CPU dentro del contenedor. No requiere internet ni costes por API. |

Variables opcionales para Whisper local:

```env
WHISPER_LOCAL_MODEL=base          # tiny, base, small, medium, large-v3
WHISPER_DEVICE=cpu                # cpu o cuda
WHISPER_COMPUTE_TYPE=int8         # int8 (rápido), float16, float32
```

### Bypass de la Detección Anti-Bot de YouTube

YouTube bloquea agresivamente las IPs de *datacenters* (típico de servidores en producción), devolviendo errores como `Sign in to confirm you're not a bot`. MathMentor IA implementa una combinación de técnicas para sortear este bloqueo:

#### 1. PO Token Provider (`bgutil-pot`)

Un *sidecar* de Docker Compose genera *Proof-of-Origin Tokens* que yt-dlp envía a YouTube para autenticar las peticiones como legítimas.

```yaml
# docker-compose.yml
bgutil-pot:
  image: brainicism/bgutil-ytdlp-pot-provider:latest
  container_name: mathmentor_bgutil_pot
  restart: unless-stopped
```

El servicio `web` se conecta a él vía:

```yaml
environment:
  - getpot_bgutil_baseurl=http://bgutil-pot:4416
```

El plugin Python `bgutil-ytdlp-pot-provider` (instalado en `requirements.txt`) hace de puente entre yt-dlp y el sidecar.

#### 2. JavaScript Runtime (Deno)

yt-dlp (desde 2026+) requiere un *runtime* de JavaScript para resolver los *n-challenges* del reproductor de YouTube. El `Dockerfile` instala **Deno** como *runtime* por defecto:

```dockerfile
RUN curl -fsSL https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip \
    && unzip /tmp/deno.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/deno
```

#### 3. EJS Challenge Solver (remote_components)

yt-dlp 2026+ descarga el *solver* de *challenges* (EJS) desde GitHub. Esto se activa con la opción `remote_components` en las opciones base de yt-dlp:

```python
# app/services/youtube_service.py
opts = {
    ...
    'remote_components': ['ejs:github'],
}
```

#### 4. Cookies de Navegador (opcional pero recomendado)

Para los vídeos más restrictivos, se pueden proporcionar *cookies* de sesión exportadas de un navegador autenticado en YouTube:

1. Instalar una extensión como **"Get cookies.txt LOCALLY"** en el navegador.
2. Abrir YouTube con una cuenta activa y exportar las *cookies* en formato Netscape.
3. Guardar el archivo como `./cookies.txt` en la raíz del proyecto.
4. Descomentar la línea del volumen en `docker-compose.yml`:

   ```yaml
   volumes:
     - ./cookies.txt:/app/cookies.txt:ro
   ```

5. Añadir en `.env`:

   ```env
   YOUTUBE_COOKIES_FILE=/app/cookies.txt
   ```

6. Reiniciar el contenedor: `docker compose restart web`

> ⚠️ **Seguridad:** `cookies.txt` contiene credenciales de sesión. Ya está incluido en `.gitignore` — **nunca lo comites al repositorio**.

> 📝 **Nota técnica:** El archivo `cookies.txt` se monta como *read-only*, pero yt-dlp necesita actualizarlo. El servicio copia automáticamente las *cookies* a `/tmp/yt_cookies.txt` (escribible) al arrancar. Ver `_get_writable_cookies_path()` en [app/services/youtube_service.py](app/services/youtube_service.py).

#### Variables de Entorno de Control

```env
# Ruta al archivo cookies.txt dentro del contenedor
YOUTUBE_COOKIES_FILE=/app/cookies.txt

# Alternativa: extraer cookies automáticamente del navegador del host
# (útil en entornos de desarrollo local; inviable en servidores sin display)
YOUTUBE_COOKIES_FROM_BROWSER=chrome

# Deshabilitar cookies forzosamente (solo usar bgutil-pot)
YOUTUBE_DISABLE_COOKIES=1
```

### Arquitectura de Bypass Completa

```
yt-dlp (Python)
   │
   ├── Cookies de navegador  ──► autenticación de sesión
   ├── bgutil-pot sidecar    ──► PO Token (Proof of Origin)
   ├── Deno                  ──► resuelve n-challenges JS
   └── ejs:github            ──► descarga solver desde GitHub
         │
         ▼
   YouTube API acepta la petición ✓
```

Las cuatro piezas son complementarias:
- **Sin `bgutil-pot`** → YouTube rechaza la petición desde IPs de *datacenter*.
- **Sin Deno** → yt-dlp falla al resolver el *n-challenge*.
- **Sin `ejs:github`** → yt-dlp no encuentra el *script solver* aunque tenga *runtime*.
- **Sin cookies** → Funciona en muchos vídeos, pero falla en los restringidos por edad o región.

### Dependencias Instaladas

Añadidas en `requirements.txt`:

```
youtube-transcript-api==0.6.2
pytubefix==10.3.5
yt-dlp>=2026.3.17                 # Mantener siempre actualizado
bgutil-ytdlp-pot-provider>=1.0.0
faster-whisper==1.1.0             # Whisper local (CPU, CTranslate2)
```

Añadidas en `Dockerfile` (paquetes del sistema):

```
ffmpeg         # requerido por faster-whisper
nodejs         # fallback de runtime JS
curl, unzip    # para descargar Deno
deno           # runtime JS por defecto de yt-dlp
```

### Diagnóstico de Problemas

**Verificar que `bgutil-pot` está activo:**
```bash
docker compose exec web curl -s http://bgutil-pot:4416/ping
```

**Verificar que Deno está instalado en el contenedor:**
```bash
docker compose exec web deno --version
```

**Probar descarga de formatos manualmente:**
```bash
docker compose exec web sh -c \
  'yt-dlp --remote-components ejs:github --cookies /app/cookies.txt -F "https://www.youtube.com/watch?v=VIDEO_ID"'
```

Si el comando anterior devuelve una lista de formatos (m4a, webm, mp4...) significa que toda la cadena funciona correctamente.

**Actualizar yt-dlp (crítico):**
YouTube cambia su reproductor con frecuencia. Si la extracción deja de funcionar, actualizar la versión de yt-dlp en `requirements.txt` y reconstruir la imagen:
```bash
docker compose build --no-cache web
docker compose up -d
```

### Migración de Bases de Datos Existentes

Si ya tienes una instalación anterior y quieres actualizar a la versión con selección de procedimientos:

```bash
# Ejecutar script de migración
docker-compose exec -T db psql -U mathmentor_user -d mathmentor < migrate_procedures.sql
```

Este script añade las columnas necesarias (`available_procedures`, `expected_procedures`, `selected_procedures`) sin perder datos existentes.

### Usuarios de Prueba

Después de ejecutar `init_db.py`, tendrás estos usuarios:

**Administrador:**
- Usuario: `admin`
- Contraseña: `admin123`

**Estudiantes:**
- Usuario: `maria`, `juan`, `lucia`
- Contraseña: `estudiante123`

⚠️ **IMPORTANTE:** Cambia estas contraseñas en producción.

## Uso de la Aplicación

### Para Administradores

1. **Subir Libros (PDF):**
   - Ir a "Libros" → "Subir Nuevo Libro"
   - Completar: Título, Curso, Materia
   - Subir PDF (máx. 50MB)
   - El sistema procesará automáticamente el PDF y extraerá temas

2. **Asignar Temas a Estudiantes:**
   - Ir a "Estudiantes"
   - Seleccionar estudiante
   - Elegir curso y temas asignados
   - Guardar

3. **Configurar Motores de IA:**
   - Editar archivo `.env`
   - Configurar `ACTIVE_AI_ENGINE` y claves API

### Para Estudiantes

1. **Practicar:**
   - Ir a "Practicar"
   - Seleccionar dificultad
   - Generar ejercicio
   - Resolver y escribir respuesta
   - Seleccionar procedimientos/técnicas utilizadas (checkboxes)
   - Enviar respuesta

2. **Sistema de Puntuación:**
   - **+10 puntos:** Respuesta correcta
   - **+5 puntos:** Metodología correcta (selección correcta de procedimientos)
   - **+3 puntos:** Reintento exitoso tras feedback
   - **Bonus:** Rachas de 3, 5, 10, 15+ ejercicios

3. **Comprar Pistas:**
   - Costo: 5 puntos
   - Proporciona orientación sin revelar la solución

4. **Ver Progreso:**
   - Ir a "Marcador" para ver estadísticas completas

## Arquitectura del Sistema

### Componentes Principales

1. **Flask Application** ([app.py](app.py))
   - Factory pattern con blueprints
   - Autenticación con Flask-Login
   - Roles: Admin y Estudiante

2. **Modelos de Base de Datos** ([app/models/](app/models/))
   - Users, StudentProfiles, Books, Topics
   - Exercises, Submissions, StudentScores
   - DocumentEmbeddings (para RAG)

3. **Servicios** ([app/services/](app/services/))
   - **PDFProcessor:** Extracción y chunking de texto
   - **RAGService:** Embeddings y búsqueda semántica
   - **ScoringService:** Lógica de gamificación

4. **Motores de IA** ([app/ai_engines/](app/ai_engines/))
   - Abstracción con clase base `AIEngine`
   - Implementaciones: OpenAI, DeepSeek, Ollama
   - Factory pattern para instanciación

### Flujo de Trabajo RAG

El sistema RAG (Retrieval-Augmented Generation) se emplea en **3 puntos clave** de la aplicación:

#### 1. Procesamiento y Almacenamiento de PDFs
**Ubicación:** `app/admin/routes.py:113-125`

Cuando el administrador sube un libro PDF:

```python
pdf_processor = PDFProcessor(chunk_size=3000, chunk_overlap=200)
rag_service = RAGService()

# Extraer y dividir el texto en chunks
chunks = pdf_processor.process_pdf(book.pdf_path)

# Generar embeddings y almacenarlos en PostgreSQL con pgvector
rag_service.store_chunks(book.id, chunks)
```

**Proceso:**
- Extrae el texto del PDF página por página usando `pdfplumber`
- Divide el contenido en chunks (fragmentos de ~3000 caracteres con 200 de superposición)
- Genera embeddings vectoriales usando `sentence-transformers/all-MiniLM-L6-v2` (384 dimensiones)
- Almacena los chunks y sus embeddings en la tabla `document_embeddings` (PostgreSQL + pgvector)

#### 2. Generación de Ejercicios
**Ubicación:** `app/student/routes.py:78-90`

Cuando un estudiante solicita un nuevo ejercicio:

```python
# Recuperar contexto relevante del libro usando RAG
rag_service = RAGService()
context = rag_service.get_context_for_topic(topic_id, top_k=3)

# Generar ejercicio usando el contexto recuperado
ai_engine = AIEngineFactory.create()
exercise_data = ai_engine.generate_exercise(
    topic=topic.topic_name,
    context=context,  # ← Contexto recuperado vía RAG
    difficulty=difficulty,
    course=profile.course
)
```

**Proceso:**
- Busca los 3 chunks más relevantes del libro usando similitud coseno (operador `<=>` de pgvector)
- El contexto recuperado se envía al modelo de IA (OpenAI/DeepSeek/Ollama)
- La IA genera un ejercicio basado en el contenido específico del libro de texto

#### 3. Generación de Pistas
**Ubicación:** `app/student/routes.py:284-288`

Cuando un estudiante compra una pista (costo: 5 puntos):

```python
# Recuperar contexto relevante
rag_service = RAGService()
context = rag_service.get_context_for_topic(exercise.topic_id, top_k=2)

# Generar pista usando el contexto
hint = ai_engine.generate_hint(exercise.content, context)
```

**Proceso:**
- Recupera los 2 chunks más relevantes del tema
- La IA genera una pista contextualizada basada en el contenido del libro
- Proporciona orientación sin revelar la solución completa

#### Arquitectura RAG

```
PDF → PDFProcessor → Chunks → RAGService → Embeddings → PostgreSQL (pgvector)
                                                              ↓
                                                     [búsqueda vectorial]
                                                              ↓
Ejercicio/Pista ← AI Engine ← Contexto recuperado ← retrieve_context()
```

**Configuración:**
- **Modelo de embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (configurable vía `EMBEDDING_MODEL` en `.env`)
- **Base de datos vectorial:** PostgreSQL 16 + extensión pgvector
- **Método de similitud:** Distancia coseno (`<=>` operator)
- **Tamaño de chunks:** 3000 caracteres con 200 de superposición

## Desarrollo

### Estructura del Proyecto

```
MathMentor IA/
├── app/
│   ├── __init__.py           # Application factory
│   ├── admin/                # Admin blueprint
│   ├── auth/                 # Authentication blueprint
│   ├── student/              # Student blueprint
│   ├── ai_engines/           # AI engine implementations
│   ├── models/               # Database models
│   ├── services/             # Business logic services
│   ├── static/               # CSS, JS
│   └── templates/            # HTML templates
├── app.py                    # Application entry point
├── init_db.py                # Database initialization script
├── docker-compose.yml        # Docker services
├── Dockerfile                # Docker image
├── requirements.txt          # Python dependencies
└── .env.example              # Environment variables template
```

### Ejecutar Tests

```bash
pytest
```

### Migraciones de Base de Datos

```bash
# Inicializar migraciones
flask db init

# Crear migración
flask db migrate -m "descripción"

# Aplicar migración
flask db upgrade
```

## Comandos Útiles

```bash
# Ver logs
docker-compose logs -f web

# Reiniciar servicios
docker-compose restart

# Detener servicios
docker-compose down

# Acceder al shell de Flask
docker-compose exec web flask shell

# Acceder a PostgreSQL
docker-compose exec db psql -U mathmentor_user -d mathmentor
```

## Configuración de Motores de IA

### OpenAI

```env
ACTIVE_AI_ENGINE=openai
ACTIVE_AI_MODEL=gpt-4
OPENAI_API_KEY=sk-...
```

### DeepSeek

```env
ACTIVE_AI_ENGINE=deepseek
ACTIVE_AI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=...
```

### Ollama (Local)

```env
ACTIVE_AI_ENGINE=ollama
ACTIVE_AI_MODEL=llama2
OLLAMA_BASE_URL=http://localhost:11434
```

## Troubleshooting

### Error: "pgvector extension not found"

Asegúrate de usar la imagen `pgvector/pgvector:pg16` en docker-compose.yml

### Error al procesar PDF

- Verifica que el PDF no esté protegido
- Tamaño máximo: 50MB
- Formato soportado: PDF

### Error de IA: "API key not configured"

Configura la clave API correspondiente en el archivo `.env`

### YouTube: "Sign in to confirm you're not a bot"

Indica que YouTube está bloqueando la IP del servidor. Verifica en orden:

1. **`bgutil-pot` está corriendo**: `docker compose ps bgutil-pot`
2. **El sidecar es alcanzable**: `docker compose exec web curl -s http://bgutil-pot:4416/ping`
3. **Deno está instalado**: `docker compose exec web deno --version`
4. **yt-dlp está actualizado**: `docker compose exec web yt-dlp --version` (debe ser ≥ 2026.3.17)
5. **Como último recurso**, proporciona un `cookies.txt` de un navegador autenticado (ver sección [Cookies de Navegador](#4-cookies-de-navegador-opcional-pero-recomendado)).

### YouTube: "Requested format is not available"

Normalmente causado por un desajuste entre el `player_client` y las *cookies*. El servicio fuerza automáticamente `player_client: ['web']` cuando hay *cookies* presentes. Si persiste, verifica que `YOUTUBE_COOKIES_FILE` apunte a un archivo válido en formato Netscape.

### YouTube: "Read-only file system: '/app/cookies.txt'"

yt-dlp necesita actualizar el archivo de *cookies*. El servicio ya maneja esto copiando las *cookies* a `/tmp/yt_cookies.txt` al arrancar. Si ves este error, verifica que `_get_writable_cookies_path()` se está ejecutando correctamente en los logs.

### Whisper: "No se detectó proveedor de Whisper"

Configura al menos uno en `.env`:
- `GROQ_API_KEY=...` (recomendado, más rápido)
- `OPENAI_API_KEY=...`
- Sin claves → el sistema usa `faster-whisper` local automáticamente (más lento, pero sin coste).

## Contribución

Este proyecto está en desarrollo activo. Las contribuciones son bienvenidas.

## Licencia

[Especifica tu licencia aquí]

## Contacto

[Tu información de contacto]
