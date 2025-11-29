"""
Teacher routes
"""
import json
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.teacher import teacher_bp
from app import db
from app.models.exercise import Exercise
from app.models.topic import Topic
from app.models.exercise_usage import ExerciseUsage
from app.models.summary import Summary
from app.models.summary_usage import SummaryUsage
from app.models.student_score import StudentScore
from app.services.rag_service import RAGService
from app.ai_engines.factory import AIEngineFactory


def teacher_required(f):
    """Decorator to require teacher/admin role"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['teacher', 'admin']:
            flash('Acceso denegado. Esta área es solo para administradores/profesores.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@teacher_bp.route('/dashboard')
@teacher_required
def dashboard():
    """Teacher dashboard with exercise bank statistics"""
    from app.models.book import Book
    from app.models.youtube_video import YouTubeVideo

    # Get filter parameters
    course_filter = request.args.get('course', '')
    source_type_filter = request.args.get('source_type', '')

    # Get exercise statistics
    total_exercises = Exercise.query.count()
    validated_exercises = Exercise.query.filter_by(status='validated').count()
    pending_exercises = Exercise.query.filter_by(status='pending_validation').count()
    auto_generated_exercises = Exercise.query.filter_by(status='auto_generated').count()
    teacher_created_exercises = Exercise.query.filter_by(status='teacher_created').count()

    # Get summary statistics
    total_summaries = Summary.query.count()
    validated_summaries = Summary.query.filter_by(status='validated').count()
    pending_summaries = Summary.query.filter_by(status='pending_validation').count()
    auto_generated_summaries = Summary.query.filter_by(status='auto_generated').count()
    teacher_created_summaries = Summary.query.filter_by(status='teacher_created').count()

    # Get statistics by topic with filtering
    topics_query = Topic.query

    # Apply source type filter
    if source_type_filter:
        topics_query = topics_query.filter_by(source_type=source_type_filter)

    # Apply course filter (requires joining with books or channels)
    if course_filter:
        from sqlalchemy import or_
        book_topics = db.session.query(Topic.id).join(Book).filter(Book.course == course_filter)
        video_topics = db.session.query(Topic.id).join(YouTubeVideo).join(
            YouTubeVideo.channel
        ).filter(db.text(f"youtube_channels.course = '{course_filter}'"))

        # Combine both queries
        topics_query = topics_query.filter(
            or_(Topic.id.in_(book_topics), Topic.id.in_(video_topics))
        )

    topics = topics_query.all()
    topic_stats = []

    # Collect unique courses and sources for filters
    all_courses = set()
    all_sources = set()

    for topic in topics:
        topic_exercises = Exercise.query.filter_by(topic_id=topic.id).count()
        topic_validated = Exercise.query.filter_by(topic_id=topic.id, status='validated').count()

        # Get source information (book or YouTube)
        source_name = 'N/A'
        course = 'N/A'
        source_type = topic.source_type

        if topic.source_type == 'pdf_book' and topic.book_id:
            book = Book.query.get(topic.book_id)
            if book:
                source_name = book.title
                course = book.course
                all_courses.add(course)
                all_sources.add(('pdf_book', source_name))
        elif topic.source_type == 'youtube_video' and topic.video_id:
            video = YouTubeVideo.query.get(topic.video_id)
            if video and video.channel:
                source_name = video.channel.channel_name
                course = video.channel.course
                all_courses.add(course)
                all_sources.add(('youtube_video', source_name))

        topic_stats.append({
            'topic': topic,
            'total': topic_exercises,
            'validated': topic_validated,
            'source_name': source_name,
            'course': course,
            'source_type': source_type
        })

    stats = {
        'total': total_exercises,
        'validated': validated_exercises,
        'pending': pending_exercises,
        'auto_generated': auto_generated_exercises,
        'teacher_created': teacher_created_exercises,
        'topic_stats': topic_stats,
        'all_courses': sorted(all_courses),
        'all_sources': sorted(all_sources, key=lambda x: x[1]),
        # Summary statistics
        'total_summaries': total_summaries,
        'validated_summaries': validated_summaries,
        'pending_summaries': pending_summaries,
        'auto_generated_summaries': auto_generated_summaries,
        'teacher_created_summaries': teacher_created_summaries
    }

    return render_template('teacher/dashboard.html',
                         stats=stats,
                         course_filter=course_filter,
                         source_type_filter=source_type_filter)


@teacher_bp.route('/exercises')
@teacher_required
def exercises():
    """List all exercises with filters"""
    # Get filter parameters
    status_filter = request.args.get('status', '')
    topic_filter = request.args.get('topic', type=int)
    difficulty_filter = request.args.get('difficulty', '')

    # Build query
    query = Exercise.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if topic_filter:
        query = query.filter_by(topic_id=topic_filter)
    if difficulty_filter:
        query = query.filter_by(difficulty=difficulty_filter)

    # Order by newest first
    exercises = query.order_by(Exercise.generated_at.desc()).all()

    # Get all topics for filter dropdown
    topics = Topic.query.all()

    return render_template('teacher/exercises.html',
                         exercises=exercises,
                         topics=topics,
                         status_filter=status_filter,
                         topic_filter=topic_filter,
                         difficulty_filter=difficulty_filter)


@teacher_bp.route('/exercise/<int:exercise_id>')
@teacher_required
def view_exercise(exercise_id):
    """View and edit a specific exercise"""
    exercise = Exercise.query.get_or_404(exercise_id)
    topic = Topic.query.get(exercise.topic_id)

    # Get usage statistics
    usage_count = ExerciseUsage.query.filter_by(exercise_id=exercise_id).count()

    return render_template('teacher/view_exercise.html',
                         exercise=exercise,
                         topic=topic,
                         usage_count=usage_count)


@teacher_bp.route('/exercise/<int:exercise_id>/edit', methods=['POST'])
@teacher_required
def edit_exercise(exercise_id):
    """Edit an exercise"""
    try:
        exercise = Exercise.query.get_or_404(exercise_id)

        data = request.json
        exercise.content = data.get('content', exercise.content)
        exercise.solution = data.get('solution', exercise.solution)
        exercise.methodology = data.get('methodology', exercise.methodology)
        exercise.difficulty = data.get('difficulty', exercise.difficulty)

        # Handle procedures
        if 'available_procedures' in data:
            exercise.available_procedures = data['available_procedures']
        if 'expected_procedures' in data:
            exercise.expected_procedures = data['expected_procedures']

        # Update metadata
        exercise.modification_notes = data.get('modification_notes', '')
        exercise.created_by_id = current_user.id

        # If it was auto-generated, change status to pending validation
        if exercise.status == 'auto_generated':
            exercise.status = 'pending_validation'

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Ejercicio actualizado correctamente'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al actualizar ejercicio: {str(e)}'
        }), 500


@teacher_bp.route('/exercise/<int:exercise_id>/validate', methods=['POST'])
@teacher_required
def validate_exercise(exercise_id):
    """Validate an exercise"""
    try:
        exercise = Exercise.query.get_or_404(exercise_id)

        exercise.status = 'validated'
        exercise.validated_by_id = current_user.id
        exercise.validated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Ejercicio validado correctamente'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al validar ejercicio: {str(e)}'
        }), 500


@teacher_bp.route('/exercise/<int:exercise_id>/delete', methods=['POST'])
@teacher_required
def delete_exercise(exercise_id):
    """Delete an exercise (includes all related submissions and usage records)"""
    try:
        exercise = Exercise.query.get_or_404(exercise_id)

        # Get usage count for confirmation message
        usage_count = ExerciseUsage.query.filter_by(exercise_id=exercise_id).count()
        submissions_count = len(exercise.submissions.all())

        # Delete exercise (cascade will automatically delete related submissions and usage records)
        db.session.delete(exercise)
        db.session.commit()

        message = f'Ejercicio eliminado correctamente'
        if usage_count > 0 or submissions_count > 0:
            message += f' (incluyendo {submissions_count} entregas de estudiantes)'

        return jsonify({
            'success': True,
            'message': message
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al eliminar ejercicio: {str(e)}'
        }), 500


@teacher_bp.route('/generate-exercises', methods=['GET', 'POST'])
@teacher_required
def generate_exercises():
    """Generate exercises in batch"""
    from app.models.book import Book
    from app.models.youtube_channel import YouTubeChannel

    topics = Topic.query.all()
    books = Book.query.all()
    channels = YouTubeChannel.query.all()

    if request.method == 'POST':
        try:
            data = request.json
            topic_ids = data.get('topic_ids', [])  # Multiple topics
            difficulty = data.get('difficulty', 'medium')
            quantity = data.get('quantity', 5)

            ai_engine = AIEngineFactory.create()
            rag_service = RAGService()
            generated_exercises = []

            for topic_id in topic_ids:
                topic = Topic.query.get(topic_id)
                if not topic:
                    continue

                # Get RAG context
                context = rag_service.get_context_for_topic(topic_id, top_k=3)
                if not context:
                    continue

                # Get source information
                source_info = topic.get_source_info()

                # Generate exercises for this topic
                for i in range(quantity):
                    exercise_data = ai_engine.generate_exercise(
                        topic=topic.topic_name,
                        context=context,
                        difficulty=difficulty,
                        course=data.get('course', 'ESO'),
                        source_info=source_info
                    )

                    # Convert solution and methodology to strings if needed
                    solution = exercise_data.get('solution', '')
                    if isinstance(solution, (dict, list)):
                        solution = json.dumps(solution, ensure_ascii=False)

                    methodology = exercise_data.get('methodology', '')
                    if isinstance(methodology, (dict, list)):
                        methodology = json.dumps(methodology, ensure_ascii=False)

                    # Create exercise with pending_validation status
                    exercise = Exercise(
                        topic_id=topic_id,
                        content=exercise_data.get('content', ''),
                        solution=solution,
                        methodology=methodology,
                        available_procedures=exercise_data.get('available_procedures', []),
                        expected_procedures=exercise_data.get('expected_procedures', []),
                        difficulty=difficulty,
                        status='pending_validation',
                        created_by_id=current_user.id
                    )
                    db.session.add(exercise)
                    generated_exercises.append(exercise)

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'{len(generated_exercises)} ejercicios generados correctamente',
                'exercise_ids': [ex.id for ex in generated_exercises]
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Error al generar ejercicios: {str(e)}'
            }), 500

    return render_template('teacher/generate_exercises.html', topics=topics, books=books, channels=channels)


@teacher_bp.route('/create-exercise', methods=['GET', 'POST'])
@teacher_required
def create_exercise():
    """Create a new exercise manually"""
    topics = Topic.query.all()

    if request.method == 'POST':
        try:
            data = request.json
            topic_id = data.get('topic_id')

            if not topic_id:
                return jsonify({
                    'success': False,
                    'message': 'Debe seleccionar un tema'
                })

            # Convert solution and methodology to strings if needed
            solution = data.get('solution', '')
            if isinstance(solution, (dict, list)):
                solution = json.dumps(solution, ensure_ascii=False)

            methodology = data.get('methodology', '')
            if isinstance(methodology, (dict, list)):
                methodology = json.dumps(methodology, ensure_ascii=False)

            # Create exercise with teacher_created status
            exercise = Exercise(
                topic_id=topic_id,
                content=data.get('content', ''),
                solution=solution,
                methodology=methodology,
                available_procedures=data.get('available_procedures', []),
                expected_procedures=data.get('expected_procedures', []),
                difficulty=data.get('difficulty', 'medium'),
                status='teacher_created',
                created_by_id=current_user.id,
                validated_by_id=current_user.id,
                validated_at=datetime.utcnow()
            )
            db.session.add(exercise)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Ejercicio creado correctamente',
                'exercise_id': exercise.id
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Error al crear ejercicio: {str(e)}'
            }), 500

    return render_template('teacher/create_exercise.html', topics=topics)


# ========== SUMMARY ROUTES ==========

@teacher_bp.route('/summaries')
@teacher_required
def summaries():
    """List all summaries with filters"""
    # Get filter parameters
    status_filter = request.args.get('status', '')
    topic_filter = request.args.get('topic', type=int)

    # Build query
    query = Summary.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if topic_filter:
        query = query.filter_by(topic_id=topic_filter)

    summaries = query.order_by(Summary.generated_at.desc()).all()
    topics = Topic.query.all()

    return render_template('teacher/summaries.html',
                         summaries=summaries,
                         topics=topics,
                         status_filter=status_filter,
                         topic_filter=topic_filter)


@teacher_bp.route('/summary/<int:summary_id>')
@teacher_required
def view_summary(summary_id):
    """View and edit a specific summary"""
    summary = Summary.query.get_or_404(summary_id)
    topic = Topic.query.get(summary.topic_id)

    # Get usage statistics
    usage_count = SummaryUsage.query.filter_by(summary_id=summary_id).count()
    total_accesses = db.session.query(db.func.sum(SummaryUsage.access_count))\
                               .filter_by(summary_id=summary_id).scalar() or 0

    return render_template('teacher/view_summary.html',
                         summary=summary,
                         topic=topic,
                         usage_count=usage_count,
                         total_accesses=total_accesses)


@teacher_bp.route('/summary/<int:summary_id>/edit', methods=['POST'])
@teacher_required
def edit_summary(summary_id):
    """Edit a summary"""
    try:
        summary = Summary.query.get_or_404(summary_id)
        data = request.json

        summary.content = data.get('content', summary.content)
        summary.modification_notes = data.get('modification_notes', '')
        summary.created_by_id = current_user.id

        # If auto-generated, change to pending validation
        if summary.status == 'auto_generated':
            summary.status = 'pending_validation'

        db.session.commit()

        return jsonify({'success': True, 'message': 'Resumen actualizado correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@teacher_bp.route('/summary/<int:summary_id>/validate', methods=['POST'])
@teacher_required
def validate_summary(summary_id):
    """Validate a summary"""
    try:
        summary = Summary.query.get_or_404(summary_id)
        summary.status = 'validated'
        summary.validated_by_id = current_user.id
        summary.validated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({'success': True, 'message': 'Resumen validado correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@teacher_bp.route('/summary/<int:summary_id>/delete', methods=['POST'])
@teacher_required
def delete_summary(summary_id):
    """Delete a summary (cascade deletes usage records)"""
    try:
        summary = Summary.query.get_or_404(summary_id)
        usage_count = SummaryUsage.query.filter_by(summary_id=summary_id).count()

        db.session.delete(summary)
        db.session.commit()

        message = 'Resumen eliminado correctamente'
        if usage_count > 0:
            message += f' (incluyendo {usage_count} registros de acceso)'

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@teacher_bp.route('/generate-summaries', methods=['GET', 'POST'])
@teacher_required
def generate_summaries():
    """Generate summaries in batch"""
    from app.models.book import Book
    from app.models.youtube_channel import YouTubeChannel

    topics = Topic.query.all()
    books = Book.query.all()
    channels = YouTubeChannel.query.all()

    if request.method == 'POST':
        try:
            data = request.json
            topic_ids = data.get('topic_ids', [])  # Multiple topics

            ai_engine = AIEngineFactory.create()
            rag_service = RAGService()
            generated_summaries = []

            for topic_id in topic_ids:
                topic = Topic.query.get(topic_id)
                if not topic:
                    continue

                # Check if summary already exists for this topic
                existing = Summary.query.filter_by(topic_id=topic_id).first()
                if existing:
                    continue  # Skip, only one summary per topic

                # Get context and generate
                context = rag_service.get_context_for_topic(topic_id, top_k=3)
                if not context:
                    continue

                # Get source information
                source_info = topic.get_source_info()

                summary_content = ai_engine.generate_topic_summary(
                    topic=topic.topic_name,
                    context=context,
                    course=data.get('course', 'ESO'),
                    source_info=source_info
                )

                # Create with pending_validation status
                summary = Summary(
                    topic_id=topic_id,
                    content=summary_content,
                    status='pending_validation',
                    created_by_id=current_user.id
                )
                db.session.add(summary)
                generated_summaries.append(summary)

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'{len(generated_summaries)} resúmenes generados',
                'summary_ids': [s.id for s in generated_summaries]
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

    return render_template('teacher/generate_summaries.html', topics=topics, books=books, channels=channels)


@teacher_bp.route('/create-summary', methods=['GET', 'POST'])
@teacher_required
def create_summary():
    """Create a new summary manually"""
    topics = Topic.query.all()

    if request.method == 'POST':
        try:
            data = request.json
            topic_id = data.get('topic_id')

            if not topic_id:
                return jsonify({'success': False, 'message': 'Debe seleccionar un tema'})

            # Check if summary already exists
            existing = Summary.query.filter_by(topic_id=topic_id).first()
            if existing:
                return jsonify({'success': False,
                              'message': 'Ya existe un resumen para este tema'})

            # Create with teacher_created status (auto-validated)
            summary = Summary(
                topic_id=topic_id,
                content=data.get('content', ''),
                status='teacher_created',
                created_by_id=current_user.id,
                validated_by_id=current_user.id,
                validated_at=datetime.utcnow()
            )
            db.session.add(summary)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Resumen creado correctamente',
                'summary_id': summary.id
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

    return render_template('teacher/create_summary.html', topics=topics)
