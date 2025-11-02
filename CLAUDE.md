# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MathMentor IA** is an AI-powered educational platform for personalized mathematics tutoring with gamification. The application generates custom math exercises from textbook PDFs, provides intelligent correction with detailed feedback, and uses a point system to motivate students.

### Key Features
- **Personalized Exercise Generation**: AI generates problems based on specific textbook content and selected topics
- **Procedure-Based Methodology**: Students select from a list of mathematical techniques/procedures instead of free-text explanations
- **Intelligent Correction with Didactic Feedback**: Analyzes solutions, detects procedural/conceptual errors, and explains mistakes
- **Gamification System**: Points awarded for correct results (+10), correct methodology (+5), effort on retry (+3), and streaks
- **RAG-Based Knowledge Base**: Textbook PDFs processed into vector database for contextualized exercises
- **Multi-AI Engine Support**: OpenAI, DeepSeek, and Ollama

### User Roles
1. **Administrator**: Manages content (uploads PDFs), selects study topics per student, configures AI engines
2. **Student**: Solves exercises, receives feedback, accumulates points, can purchase hints with points

## Technical Stack

- **Backend**: Flask (Python)
- **Database**: PostgreSQL with pgvector extension
- **Deployment**: Docker Compose
- **AI Engines**: OpenAI, DeepSeek, Ollama
- **Frontend**: Bootstrap 5, JavaScript

## Project Status

✅ **Fully Implemented** - The application is complete and ready to use. See README.md for setup instructions.

## Common Development Commands

### Docker Commands
```bash
# Start application stack
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down

# Restart services
docker-compose restart
```

### Database Commands
```bash
# Initialize database with test users
docker-compose exec web python init_db.py

# Flask migrations
docker-compose exec web flask db init
docker-compose exec web flask db migrate -m "message"
docker-compose exec web flask db upgrade

# Access PostgreSQL
docker-compose exec db psql -U mathmentor_user -d mathmentor
```

## Implementation Details

### Project Structure
app/
├── __init__.py              # Application factory
├── admin/                   # Admin blueprint (books, students, topics)
├── auth/                    # Authentication (login/logout)
├── student/                 # Student blueprint (practice, scoreboard)
├── ai_engines/              # AI abstraction layer
├── models/                  # SQLAlchemy models
├── services/                # Business logic (PDF, RAG, Scoring)
├── static/                  # CSS, JavaScript
└── templates/               # Jinja2 templates

### Key Design Patterns

1. **Factory Pattern**: AIEngineFactory creates engine instances based on configuration
2. **Blueprint Pattern**: Modular Flask blueprints (admin, auth, student)
3. **Service Layer**: Business logic separated from routes
4. **Strategy Pattern**: Different AI engines implementing common interface

### Procedure Selection System

Located in [app/models/exercise.py](app/models/exercise.py) and [app/templates/student/practice.html](app/templates/student/practice.html):

When AI generates an exercise, it creates:
- `available_procedures`: List of all mathematical procedures/techniques (both correct and incorrect options)
  - Example: `[{"id": 1, "name": "Propiedad distributiva", "description": "Permite multiplicar un término por una suma"}, {"id": 2, "name": "Teorema de Pitágoras", "description": "Relaciona los lados de un triángulo rectángulo"}]`
- `expected_procedures`: List of procedure IDs that should be selected for correct methodology
  - Example: `[1, 3, 5]`

Students select procedures via checkboxes with interactive tooltips:
- **Hover tooltip**: Shows procedure name and description when hovering over the label
- **Info icon**: Visual indicator that additional information is available
- **Custom styling**: Enhanced UX with hover effects and proper spacing

Methodology is evaluated by comparing:
- `selected_procedures` (from student) with `expected_procedures` (from exercise)
- Methodology is correct if all expected procedures are selected (subset match)

### Scoring System

Located in [app/services/scoring_service.py](app/services/scoring_service.py):
- POINTS_CORRECT_RESULT = 10
- POINTS_CORRECT_METHODOLOGY = 5
- POINTS_EFFORT_RETRY = 3
- HINT_COST = 5
- Streak Bonuses: 3→+2, 5→+5, 10→+10, 15→+20

### AI Engine Switching

Change engine by modifying .env:
```
ACTIVE_AI_ENGINE=openai  # or deepseek, ollama
ACTIVE_AI_MODEL=gpt-4    # or deepseek-chat, llama2
```

## Testing

Test users (created by init_db.py):
- Admin: username=admin, password=admin123
- Students: username=maria/juan/lucia, password=estudiante123

⚠️ Change passwords in production!

## Troubleshooting

- **pgvector Issues**: Ensure using pgvector/pgvector:pg16 image
- **PDF Processing**: Check PDF is not password-protected, size < 50MB
- **AI API Errors**: Verify API key is set in .env
