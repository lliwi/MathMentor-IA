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

4. **Inicializar la base de datos:**
```bash
docker-compose exec web python init_db.py
```

5. **Acceder a la aplicación:**
- Abrir navegador en: http://localhost:5000

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

```
PDF → Extracción → Chunking → Embeddings → PostgreSQL+pgvector
                                              ↓
Tema del Estudiante → Búsqueda Semántica → Contexto → Generación de Ejercicio (IA)
```

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

## Contribución

Este proyecto está en desarrollo activo. Las contribuciones son bienvenidas.

## Licencia

[Especifica tu licencia aquí]

## Contacto

[Tu información de contacto]
