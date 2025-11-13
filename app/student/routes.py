"""
Student routes
"""
import random
import threading
from flask import render_template, redirect, url_for, flash, request, jsonify, session, current_app
from flask_login import login_required, current_user
from functools import wraps
from app.student import student_bp
from app import db
from app.models.exercise import Exercise
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.student_profile import StudentProfile
from app.services.rag_service import RAGService
from app.services.scoring_service import ScoringService
from app.services.analytics_service import AnalyticsService
from app.ai_engines.factory import AIEngineFactory


def student_required(f):
    """Decorator to require student role"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'student':
            flash('Acceso denegado. Esta área es solo para estudiantes.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@student_bp.route('/dashboard')
@student_required
def dashboard():
    """Student dashboard"""
    stats = ScoringService.get_student_statistics(current_user.id)
    return render_template('student/dashboard.html', stats=stats)


def _prefetch_contexts_background(app, topic_ids):
    """Background task to prefetch RAG contexts"""
    with app.app_context():
        try:
            rag_service = RAGService()
            # Prefetch context for first 3 topics (most likely to be used)
            for topic_id in topic_ids[:3]:
                # This will cache the context via @cache_service.cache_context decorator
                rag_service.get_context_for_topic(topic_id, top_k=3)
            print(f"[Practice] Prefetched RAG context for {min(3, len(topic_ids))} topics")
        except Exception as e:
            # Background task failure shouldn't affect user
            print(f"[Practice] Warning: Context prefetch failed: {e}")


@student_bp.route('/practice')
@student_required
def practice():
    """Practice area - generate and solve exercises"""
    stats = ScoringService.get_student_statistics(current_user.id)

    # Prefetch RAG context in background to warm up cache (non-blocking)
    try:
        profile = current_user.student_profile
        if profile:
            topic_ids = profile.get_topics()
            if topic_ids:
                # Start background thread for prefetching with app context
                app = current_app._get_current_object()
                thread = threading.Thread(target=_prefetch_contexts_background, args=(app, topic_ids))
                thread.daemon = True
                thread.start()
                print(f"[Practice] Started background prefetch for {len(topic_ids)} topics")
    except Exception as e:
        # Don't fail the page load if prefetch fails
        print(f"[Practice] Warning: Could not start prefetch: {e}")

    # Get student's assigned topics
    topics = []
    if profile:
        topic_ids = profile.get_topics()
        if topic_ids:
            topics = Topic.query.filter(Topic.id.in_(topic_ids)).all()
    
    return render_template('student/practice.html', stats=stats, topics=topics)


@student_bp.route('/generate-exercise', methods=['POST'])
@student_required
def generate_exercise():
    """Generate a new exercise for the student"""
    try:
        # Get student profile
        profile = current_user.student_profile
        if not profile:
            return jsonify({
                'success': False,
                'message': 'No tienes un perfil configurado. Contacta al administrador.'
            })

        # Get assigned topics
        topic_ids = profile.get_topics()
        if not topic_ids:
            return jsonify({
                'success': False,
                'message': 'No tienes temas asignados. Contacta al administrador.'
            })

        # Select a random topic
        topic_id = random.choice(topic_ids)
        topic = Topic.query.get(topic_id)

        if not topic:
            return jsonify({
                'success': False,
                'message': 'Error al cargar el tema.'
            })

        # Get context from RAG
        rag_service = RAGService()
        context = rag_service.get_context_for_topic(topic_id, top_k=3)

        # Get list of completed exercise IDs to prevent duplicates
        completed_exercise_ids = AnalyticsService.get_completed_exercise_ids(current_user.id)

        # Generate exercise using AI
        ai_engine = AIEngineFactory.create()
        difficulty = request.json.get('difficulty', 'medium')

        # Try to generate a unique exercise (max 3 attempts)
        max_attempts = 3
        exercise = None

        for attempt in range(max_attempts):
            exercise_data = ai_engine.generate_exercise(
                topic=topic.topic_name,
                context=context,
                difficulty=difficulty,
                course=profile.course
            )

            # Create exercise object
            new_exercise = Exercise(
                topic_id=topic_id,
                content=exercise_data.get('content', ''),
                solution=exercise_data.get('solution', ''),
                methodology=exercise_data.get('methodology', ''),
                available_procedures=exercise_data.get('available_procedures', []),
                expected_procedures=exercise_data.get('expected_procedures', []),
                difficulty=difficulty
            )
            db.session.add(new_exercise)
            db.session.flush()  # Get ID without committing

            # Check if this exercise is unique (content-based check)
            is_duplicate = False
            if completed_exercise_ids:
                existing = Exercise.query.filter(
                    Exercise.id.in_(completed_exercise_ids),
                    Exercise.content == new_exercise.content
                ).first()

                if existing:
                    is_duplicate = True
                    db.session.rollback()
                    print(f"[Practice] Duplicate exercise detected (attempt {attempt + 1}), regenerating...")
                    continue  # Try again

            # Not a duplicate, commit and use this exercise
            exercise = new_exercise
            db.session.commit()
            break

        # If still None after max attempts, generate one final time and use it
        if exercise is None:
            print(f"[Practice] Warning: Could not generate unique exercise after {max_attempts} attempts, using last one")
            exercise_data = ai_engine.generate_exercise(
                topic=topic.topic_name,
                context=context,
                difficulty=difficulty,
                course=profile.course
            )
            exercise = Exercise(
                topic_id=topic_id,
                content=exercise_data.get('content', ''),
                solution=exercise_data.get('solution', ''),
                methodology=exercise_data.get('methodology', ''),
                available_procedures=exercise_data.get('available_procedures', []),
                expected_procedures=exercise_data.get('expected_procedures', []),
                difficulty=difficulty
            )
            db.session.add(exercise)
            db.session.commit()

        # Store exercise ID in session
        session['current_exercise_id'] = exercise.id

        return jsonify({
            'success': True,
            'exercise': {
                'id': exercise.id,
                'content': exercise.content,
                'topic': topic.topic_name,
                'difficulty': difficulty,
                'available_procedures': exercise.available_procedures or []
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al generar ejercicio: {str(e)}'
        })


@student_bp.route('/submit-exercise', methods=['POST'])
@student_required
def submit_exercise():
    """Submit an exercise solution for correction"""
    try:
        data = request.json
        exercise_id = data.get('exercise_id')
        student_answer = data.get('answer', '')
        student_methodology = data.get('methodology', '')
        selected_procedures = data.get('selected_procedures', [])
        is_retry = data.get('is_retry', False)

        # Get exercise
        exercise = Exercise.query.get(exercise_id)
        if not exercise:
            return jsonify({
                'success': False,
                'message': 'Ejercicio no encontrado'
            })

        # Evaluate using AI
        ai_engine = AIEngineFactory.create()
        evaluation = ai_engine.evaluate_submission(
            exercise=exercise.content,
            expected_solution=exercise.solution,
            expected_methodology=exercise.methodology,
            student_answer=student_answer,
            student_methodology=student_methodology
        )

        # Evaluate procedure selection
        is_correct_methodology = evaluation.get('is_correct_methodology', False)
        if exercise.expected_procedures and selected_procedures:
            # Check if selected procedures match expected ones
            expected_set = set(exercise.expected_procedures)
            selected_set = set(selected_procedures)

            # Methodology is correct if selected procedures match expected ones
            # (or at least contain all expected procedures)
            if expected_set.issubset(selected_set):
                is_correct_methodology = True
            else:
                is_correct_methodology = False

        # Calculate score
        score_data = ScoringService.calculate_score(
            is_correct_result=evaluation.get('is_correct_result', False),
            is_correct_methodology=is_correct_methodology,
            is_retry=is_retry
        )

        # Create submission
        submission = Submission(
            student_id=current_user.id,
            exercise_id=exercise_id,
            answer=student_answer,
            methodology=student_methodology,
            selected_procedures=selected_procedures,
            is_correct_result=evaluation.get('is_correct_result', False),
            is_correct_methodology=is_correct_methodology,
            score_result=score_data['score_result'],
            score_development=score_data['score_development'],
            score_effort=score_data['score_effort'],
            total_score=score_data['total_score'],
            feedback=evaluation.get('feedback', ''),
            is_retry=is_retry
        )
        db.session.add(submission)
        db.session.commit()

        # Update student score
        score_update = ScoringService.update_student_score(current_user.id, submission)

        # Generate detailed feedback if incorrect
        detailed_feedback = evaluation.get('feedback', '')
        if not evaluation.get('is_correct_result', False) and evaluation.get('errors_found'):
            detailed_feedback = ai_engine.generate_feedback(
                exercise=exercise.content,
                student_answer=student_answer,
                student_methodology=student_methodology,
                errors=evaluation.get('errors_found', [])
            )

        # Only include solution on retry (second attempt)
        response_data = {
            'is_correct': evaluation.get('is_correct_result', False),
            'is_methodology_correct': is_correct_methodology,
            'feedback': detailed_feedback,
            'score': score_data['total_score'],
            'score_breakdown': score_data,
            'total_points': score_update['total_points'],
            'available_points': score_update['available_points'],
            'current_streak': score_update['current_streak'],
            'streak_bonus': score_update['streak_bonus'],
            'is_retry': is_retry  # Send back retry status
        }

        # Include solution only if this was a retry attempt
        if is_retry:
            response_data['solution'] = exercise.solution

        return jsonify({
            'success': True,
            'evaluation': response_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al evaluar ejercicio: {str(e)}'
        })


@student_bp.route('/scoreboard')
@student_required
def scoreboard():
    """View personal scoreboard and statistics"""
    stats = ScoringService.get_student_statistics(current_user.id)

    # Get recent submissions
    recent_submissions = Submission.query.filter_by(
        student_id=current_user.id
    ).order_by(Submission.submitted_at.desc()).limit(10).all()

    return render_template('student/scoreboard.html',
                         stats=stats,
                         recent_submissions=recent_submissions)


@student_bp.route('/buy-hint', methods=['POST'])
@student_required
def buy_hint():
    """Purchase a hint using points"""
    try:
        data = request.json
        exercise_id = data.get('exercise_id')

        # Get exercise
        exercise = Exercise.query.get(exercise_id)
        if not exercise:
            return jsonify({
                'success': False,
                'message': 'Ejercicio no encontrado'
            })

        # Purchase hint
        success, message = ScoringService.purchase_hint(current_user.id)

        if not success:
            return jsonify({
                'success': False,
                'message': message
            })

        # Generate hint using AI
        ai_engine = AIEngineFactory.create()

        # Get context
        rag_service = RAGService()
        context = rag_service.get_context_for_topic(exercise.topic_id, top_k=2)

        hint = ai_engine.generate_hint(exercise.content, context)

        return jsonify({
            'success': True,
            'hint': hint,
            'message': message
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al generar pista: {str(e)}'
        })


@student_bp.route("/buy-summary", methods=["POST"])
@student_required
def buy_summary():
    """Purchase a topic summary using points"""
    try:
        data = request.json
        topic_id = data.get("topic_id")

        # Get topic
        topic = Topic.query.get(topic_id)
        if not topic:
            return jsonify({"success": False, "message": "Tema no encontrado"})

        # Check if student has this topic assigned
        profile = current_user.student_profile
        if not profile or topic_id not in profile.get_topics():
            return jsonify({"success": False, "message": "No tienes este tema asignado"})

        # Purchase summary
        success, message = ScoringService.purchase_summary(current_user.id)
        if not success:
            return jsonify({"success": False, "message": message})

        # Generate summary using AI
        ai_engine = AIEngineFactory.create()
        rag_service = RAGService()
        context = rag_service.get_context_for_topic(topic_id, top_k=5)

        summary = ai_engine.generate_topic_summary(
            topic=topic.topic_name,
            context=context,
            course=profile.course
        )

        # Get updated stats
        stats = ScoringService.get_student_statistics(current_user.id)

        return jsonify({
            "success": True,
            "summary": summary,
            "topic_name": topic.topic_name,
            "message": message,
            "available_points": stats["available_points"]
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Error al generar resumen: {str(e)}"})

