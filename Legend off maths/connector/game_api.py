"""
Legend of Maths — Conector API (Fase 0)

Capa JSON fina sobre MathMentor IA. NO reimplementa lógica de negocio:
reutiliza por importación los servicios y las vistas JSON ya existentes del
blueprint `student` de MathMentor (generación de ejercicios con IA, corrección,
puntuación, pistas y resúmenes). MathMentor sigue siendo la fuente de verdad.

Este módulo solo aporta:
  - Autenticación JSON (login/logout) reutilizando el modelo User y flask_login.
  - Un endpoint de estado (/me) con puntos, racha, estadísticas y temas.
  - Reexposición de los flujos de MathMentor bajo /api/game/* para el cliente Phaser.
  - Servido estático del juego Phaser 3 en /legend.

Ningún archivo del proyecto original se modifica.
"""
from functools import wraps
from pathlib import Path

from flask import Blueprint, request, jsonify, send_from_directory
from flask_login import login_user, logout_user, current_user

# --- Importaciones del proyecto original MathMentor (sin modificarlo) ---
from app.models.user import User
from app.models.topic import Topic
from app.services.scoring_service import ScoringService

# Reutilización directa de las vistas JSON existentes (misma lógica, sin copiarla)
import app.student.routes as _mm_routes
from app.student.routes import (
    generate_exercise as mm_generate_exercise,
    submit_exercise as mm_submit_exercise,
    buy_hint as mm_buy_hint,
    buy_summary as mm_buy_summary,
)

# Shim (sin modificar el original): buy_summary usa `datetime` como global del módulo
# en la rama de re-acceso a un resumen ya comprado, pero routes.py solo importa datetime
# localmente dentro de scoreboard(). Definimos el global aquí para que el flujo
# reutilizado no lance NameError. Es un parche en tiempo de ejecución del conector.
import datetime as _datetime
if not isinstance(getattr(_mm_routes, 'datetime', None), type):
    _mm_routes.datetime = _datetime.datetime

game_api = Blueprint('game_api', __name__, url_prefix='/api/game')


def game_login_required(f):
    """Como login_required pero responde JSON 401/403 en lugar de redirigir a HTML."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'auth': False,
                            'message': 'No autenticado'}), 401
        if current_user.role != 'student':
            return jsonify({'success': False,
                            'message': 'Solo cuentas de estudiante pueden jugar'}), 403
        return f(*args, **kwargs)
    return wrapper


# --------------------------------------------------------------------------- #
#  Autenticación (aporta el conector)
# --------------------------------------------------------------------------- #
@game_api.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Credenciales inválidas'}), 401
    if user.role != 'student':
        return jsonify({'success': False,
                        'message': 'Solo cuentas de estudiante pueden jugar'}), 403

    login_user(user)
    return jsonify({'success': True,
                    'user': {'id': user.id, 'username': user.username}})


@game_api.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'success': True})


@game_api.route('/me', methods=['GET'])
@game_login_required
def me():
    """Estado del jugador para el HUD: puntos, racha, estadísticas y temas asignados."""
    from app.models.summary import Summary
    from app.models.summary_usage import SummaryUsage

    stats = ScoringService.get_student_statistics(current_user.id)
    profile = current_user.student_profile

    # Temas cuyo resumen ya posee el estudiante (re-acceso gratuito).
    owned = set()
    for usage in SummaryUsage.query.filter_by(student_id=current_user.id).all():
        s = Summary.query.get(usage.summary_id)
        if s:
            owned.add(s.topic_id)

    topics = []
    if profile:
        for tid in profile.get_topics():
            topic = Topic.query.get(tid)
            if topic:
                topics.append({'id': topic.id, 'name': topic.topic_name,
                               'owned': topic.id in owned})

    return jsonify({
        'success': True,
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'course': profile.course if profile else None,
        },
        'stats': stats,
        'topics': topics,
    })


# --------------------------------------------------------------------------- #
#  Flujos reutilizados de MathMentor (la lógica vive allí, aquí solo se enrutan)
# --------------------------------------------------------------------------- #
@game_api.route('/exercise', methods=['POST'])
@game_login_required
def exercise():
    """Genera/obtiene un ejercicio (banco o IA). Reutiliza student.generate_exercise."""
    return mm_generate_exercise()


@game_api.route('/submit', methods=['POST'])
@game_login_required
def submit():
    """Corrige la respuesta y actualiza puntuación. Reutiliza student.submit_exercise."""
    return mm_submit_exercise()


@game_api.route('/hint', methods=['POST'])
@game_login_required
def hint():
    """Compra una pista gastando puntos reales. Reutiliza student.buy_hint."""
    return mm_buy_hint()


@game_api.route('/summary', methods=['POST'])
@game_login_required
def summary():
    """Compra/accede a un resumen de tema. Reutiliza student.buy_summary."""
    return mm_buy_summary()


# --------------------------------------------------------------------------- #
#  Servido estático del juego Phaser 3
# --------------------------------------------------------------------------- #
def init_game_static(app, game_root):
    """Sirve el cliente Phaser en /legend (mismo origen → la cookie de sesión se comparte)."""
    game_dir = Path(game_root) / 'game'

    @app.route('/legend')
    @app.route('/legend/')
    def legend_index():
        return send_from_directory(game_dir, 'index.html')

    @app.route('/legend/<path:filename>')
    def legend_static(filename):
        return send_from_directory(game_dir, filename)
