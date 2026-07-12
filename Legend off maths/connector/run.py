"""
Legend of Maths — Punto de entrada del conector (Fase 0)

Construye la app Flask de MathMentor mediante su factory `create_app()` (sin
modificar el proyecto original), le registra el blueprint del juego y sirve el
cliente Phaser 3. Como es la MISMA app Flask, comparte base de datos, sesión,
login_manager y todos los servicios/IA del proyecto original.

Ejecutar (desde cualquier sitio):
    python "Legend off maths/connector/run.py"

Nota: este archivo se llama run.py (no app.py) para no colisionar con el paquete
`app` de MathMentor al importarlo.

Requiere el .env de MathMentor (DATABASE_URL, claves de IA, SECRET_KEY, ...).
"""
import os
import sys
from pathlib import Path

CONNECTOR_DIR = Path(__file__).resolve().parent          # .../Legend off maths/connector
GAME_ROOT = CONNECTOR_DIR.parent                         # .../Legend off maths
PROJECT_ROOT = GAME_ROOT.parent                          # .../nomasceros.es (MathMentor)

# Hacer importables tanto el paquete `app` de MathMentor como este conector.
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CONNECTOR_DIR))

# Cargar el .env de MathMentor y situarse en su raíz para que las rutas
# relativas (uploads, etc.) resuelvan igual que en la app original.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(PROJECT_ROOT / '.env')
os.chdir(PROJECT_ROOT)

from app import create_app          # noqa: E402  factory de MathMentor (intacta)
import game_api as game_api_module  # noqa: E402  conector (módulo sibling)


def build_app():
    app = create_app()
    app.register_blueprint(game_api_module.game_api)      # /api/game/*
    game_api_module.init_game_static(app, GAME_ROOT)      # /legend
    return app


app = build_app()


if __name__ == '__main__':
    port = int(os.getenv('LEGEND_PORT', '5055'))
    # En producción (FLASK_ENV=production) no se activa el modo debug.
    debug = os.getenv('FLASK_ENV', 'development') != 'production'
    print(f"\n🎮 Legend of Maths conectado a MathMentor IA")
    print(f"   Juego:  http://localhost:{port}/legend")
    print(f"   API:    http://localhost:{port}/api/game/*\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
