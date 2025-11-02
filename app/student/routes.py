"""
Student routes
"""
import random
from flask import render_template, redirect, url_for, flash, request, jsonify, session
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


@student_bp.route('/practice')
@student_required
def practice():
    """Practice area - generate and solve exercises"""
    stats = ScoringService.get_student_statistics(current_user.id)
    return render_template('student/practice.html', stats=stats)


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

        # Generate exercise using AI
        ai_engine = AIEngineFactory.create()
        difficulty = request.json.get('difficulty', 'medium')

        exercise_data = ai_engine.generate_exercise(
            topic=topic.topic_name,
            context=context,
            difficulty=difficulty,
            course=profile.course
        )

        # Save exercise to database
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
