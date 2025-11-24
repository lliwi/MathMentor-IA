"""
Student routes
"""
import json
import random
import threading
import time
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
from app.services.cache_service import CacheService
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


def _prefetch_exercises_background(app, topic_ids, course, student_id):
    """Background task to prefetch exercises for all difficulties into pool"""
    import time as time_module

    with app.app_context():
        try:
            # Small delay to ensure RAG model is initialized
            time_module.sleep(2)

            rag_service = RAGService()
            ai_engine = AIEngineFactory.create()
            cache_service = CacheService()

            # Get student's completed exercises to avoid duplicates
            completed_exercise_contents = AnalyticsService.get_completed_exercise_contents(student_id)

            prefetch_count = 0
            difficulties = ['easy', 'medium', 'hard']

            # Prefetch for first 2 topics, all difficulties
            for topic_id in topic_ids[:2]:
                topic = Topic.query.get(topic_id)
                if not topic:
                    continue

                # Get context (likely already cached)
                context = rag_service.get_context_for_topic(topic_id, top_k=2)
                if not context:
                    continue

                # Generate one exercise per difficulty level
                for difficulty in difficulties:
                    max_attempts = 3  # Try up to 3 times to get unique exercise

                    for attempt in range(max_attempts):
                        # Generate exercise
                        exercise_data = ai_engine.generate_exercise(
                            topic=topic.topic_name,
                            context=context,
                            difficulty=difficulty,
                            course=course
                        )

                        # Check if this exercise content is unique
                        exercise_content = exercise_data.get('content', '')
                        if exercise_content not in completed_exercise_contents:
                            # Add to pool (pool will also check internal duplicates)
                            cache_service.add_exercise_to_pool(
                                topic=topic.topic_name,
                                difficulty=difficulty,
                                course=course,
                                exercise_data=exercise_data,
                                pool_size=5
                            )
                            prefetch_count += 1
                            break  # Got unique exercise, move to next difficulty

            print(f"[Practice] Prefetched {prefetch_count} unique exercises into pool (all difficulties)")
        except Exception as e:
            print(f"[Practice] Warning: Exercise prefetch failed: {e}")


@student_bp.route('/practice')
@student_required
def practice():
    """Practice area - generate and solve exercises"""
    stats = ScoringService.get_student_statistics(current_user.id)

    # Prefetch RAG context and exercises in background to warm up cache (non-blocking)
    try:
        profile = current_user.student_profile
        if profile:
            topic_ids = profile.get_topics()
            if topic_ids:
                # Start background thread for prefetching contexts
                app = current_app._get_current_object()
                context_thread = threading.Thread(target=_prefetch_contexts_background, args=(app, topic_ids))
                context_thread.daemon = True
                context_thread.start()

                # Start background thread for prefetching exercises (all difficulties)
                exercise_thread = threading.Thread(target=_prefetch_exercises_background, args=(app, topic_ids, profile.course, current_user.id))
                exercise_thread.daemon = True
                exercise_thread.start()

                print(f"[Practice] Started background prefetch for {len(topic_ids)} topics (contexts + 3 difficulties)")
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


def _prefetch_next_exercise_background(app, topic_id, course, student_id, difficulty):
    """Background task to prefetch next exercise while student is working"""
    with app.app_context():
        try:
            rag_service = RAGService()
            ai_engine = AIEngineFactory.create()
            cache_service = CacheService()
            topic = Topic.query.get(topic_id)

            if not topic:
                return

            context = rag_service.get_context_for_topic(topic_id, top_k=2)
            if not context:
                return

            # Get student's completed exercises
            completed_exercise_contents = AnalyticsService.get_completed_exercise_contents(student_id)

            # Try to generate unique exercise and add to pool
            for attempt in range(3):
                exercise_data = ai_engine.generate_exercise(
                    topic=topic.topic_name,
                    context=context,
                    difficulty=difficulty,
                    course=course
                )

                # Check uniqueness
                exercise_content = exercise_data.get('content', '')
                if exercise_content not in completed_exercise_contents:
                    # Add to pool (pool will also check internal duplicates)
                    cache_service.add_exercise_to_pool(
                        topic=topic.topic_name,
                        difficulty=difficulty,
                        course=course,
                        exercise_data=exercise_data,
                        pool_size=5
                    )
                    print(f"[RollingPrefetch] Added exercise to pool ({difficulty}) for topic {topic_id}")
                    break

        except Exception as e:
            print(f"[RollingPrefetch] Warning: {e}")


@student_bp.route('/prefetch-next', methods=['POST'])
@student_required
def prefetch_next():
    """Prefetch next exercise while student is working (rolling prefetch)"""
    try:
        data = request.get_json()
        topic_id = data.get('topic_id')
        difficulty = data.get('difficulty', 'medium')

        profile = current_user.student_profile
        if not profile or not topic_id:
            return jsonify({'success': False})

        # Start background prefetch
        app = current_app._get_current_object()
        thread = threading.Thread(
            target=_prefetch_next_exercise_background,
            args=(app, topic_id, profile.course, current_user.id, difficulty)
        )
        thread.daemon = True
        thread.start()

        return jsonify({'success': True})

    except Exception as e:
        print(f"[RollingPrefetch] Error: {e}")
        return jsonify({'success': False})


@student_bp.route('/generate-exercise', methods=['POST'])
@student_required
def generate_exercise():
    """Generate a new exercise for the student using pool-based caching"""
    try:
        start_total = time.time()

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

        difficulty = request.json.get('difficulty', 'medium')
        cache_service = CacheService()

        # Get list of completed exercise contents to prevent duplicates
        start_completed = time.time()
        completed_exercise_contents = AnalyticsService.get_completed_exercise_contents(current_user.id)
        completed_time = time.time() - start_completed
        print(f"[TIMING] Get completed exercises ({len(completed_exercise_contents)} total): {completed_time:.3f}s")

        # Try to get exercise from pool first
        start_pool = time.time()
        exercise_data = cache_service.get_exercise_from_pool(
            topic=topic.topic_name,
            difficulty=difficulty,
            course=profile.course,
            completed_exercise_contents=completed_exercise_contents
        )
        pool_time = time.time() - start_pool
        print(f"[TIMING] Pool lookup: {pool_time:.3f}s")

        # If no exercise in pool, generate a new one
        if not exercise_data:
            print(f"[Practice] Pool empty/exhausted - generating new exercise")

            # Get context from RAG
            start_rag = time.time()
            rag_service = RAGService()
            context = rag_service.get_context_for_topic(topic_id, top_k=2)
            rag_time = time.time() - start_rag
            print(f"[TIMING] RAG context retrieval: {rag_time:.3f}s")

            # Generate exercise using AI
            start_ai = time.time()
            ai_engine = AIEngineFactory.create()
            exercise_data = ai_engine.generate_exercise(
                topic=topic.topic_name,
                context=context,
                difficulty=difficulty,
                course=profile.course
            )
            ai_time = time.time() - start_ai
            print(f"[TIMING] AI exercise generation: {ai_time:.3f}s")

            # Add to pool for future use
            cache_service.add_exercise_to_pool(
                topic=topic.topic_name,
                difficulty=difficulty,
                course=profile.course,
                exercise_data=exercise_data,
                pool_size=5
            )

        # Convert solution and methodology to strings if they are dict/list
        solution = exercise_data.get('solution', '')
        if isinstance(solution, (dict, list)):
            solution = json.dumps(solution, ensure_ascii=False)

        methodology = exercise_data.get('methodology', '')
        if isinstance(methodology, (dict, list)):
            methodology = json.dumps(methodology, ensure_ascii=False)

        # Create exercise object in database
        start_db = time.time()
        exercise = Exercise(
            topic_id=topic_id,
            content=exercise_data.get('content', ''),
            solution=solution,
            methodology=methodology,
            available_procedures=exercise_data.get('available_procedures', []),
            expected_procedures=exercise_data.get('expected_procedures', []),
            difficulty=difficulty
        )
        db.session.add(exercise)
        db.session.commit()
        db_time = time.time() - start_db
        print(f"[TIMING] Database save: {db_time:.3f}s")

        # Store exercise ID in session
        session['current_exercise_id'] = exercise.id

        total_time = time.time() - start_total
        print(f"[TIMING] TOTAL generate_exercise: {total_time:.3f}s")

        return jsonify({
            'success': True,
            'exercise': {
                'id': exercise.id,
                'content': exercise.content,
                'topic': topic.topic_name,
                'topic_id': topic_id,
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
                expected_solution=exercise.solution,
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
    """Purchase a hint using points - progressive hints system"""
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

        # Track hints purchased per exercise in session
        if 'hints_purchased' not in session:
            session['hints_purchased'] = {}

        hints_purchased = session['hints_purchased']
        exercise_key = str(exercise_id)
        hint_count = hints_purchased.get(exercise_key, 0)

        # Check if already purchased 2 hints for this exercise
        if hint_count >= 2:
            return jsonify({
                'success': False,
                'message': 'Ya has comprado todas las pistas disponibles para este ejercicio'
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

        # First hint: textual hint
        # Second hint: visual scheme
        if hint_count == 0:
            # First hint - textual
            hint = ai_engine.generate_hint(exercise.content, context)
            hint_type = 'text'
            hint_level = 1
        else:
            # Second hint - visual scheme
            hint = ai_engine.generate_visual_scheme(exercise.content, context)
            hint_type = 'visual'
            hint_level = 2

        # Update hints purchased count
        hints_purchased[exercise_key] = hint_count + 1
        session['hints_purchased'] = hints_purchased
        session.modified = True

        return jsonify({
            'success': True,
            'hint': hint,
            'hint_type': hint_type,
            'hint_level': hint_level,
            'hints_remaining': 2 - (hint_count + 1),
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
        context = rag_service.get_context_for_topic(topic_id, top_k=3)

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

