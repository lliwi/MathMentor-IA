"""
Admin routes
"""
import os
import sys
import json
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.admin import admin_bp
from app.admin.forms import UploadBookForm, EditBookForm, CreateStudentForm, EditStudentForm, CreateAdminForm, EditAdminForm, AddYouTubeChannelForm
from app import db
from app.models.book import Book
from app.models.course import Course
from app.models.topic import Topic
from app.models.user import User
from app.models.student_profile import StudentProfile
from app.models.youtube_channel import YouTubeChannel
from app.models.youtube_video import YouTubeVideo
from app.services.pdf_processor import PDFProcessor
from app.services.rag_service import RAGService
from app.services.analytics_service import AnalyticsService
from app.services.youtube_service import YouTubeService
from app.services.backup_service import BackupService
from app.ai_engines.factory import AIEngineFactory
from flask import Response, send_file


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard"""
    books_count = Book.query.count()
    channels_count = YouTubeChannel.query.count()
    students_count = User.query.filter_by(role='student').count()
    admins_count = User.query.filter_by(role='admin').count()
    topics_count = Topic.query.count()

    return render_template('admin/dashboard.html',
                         books_count=books_count,
                         channels_count=channels_count,
                         students_count=students_count,
                         admins_count=admins_count,
                         topics_count=topics_count)


@admin_bp.route('/books')
@admin_required
def books():
    """Manage books"""
    all_books = Book.query.order_by(Book.uploaded_at.desc()).all()
    return render_template('admin/books.html', books=all_books)


@admin_bp.route('/books/upload', methods=['GET', 'POST'])
@admin_required
def upload_book():
    """Upload a new book (PDF)"""
    form = UploadBookForm()

    # Populate course choices from database
    active_courses = Course.query.filter_by(active=True).order_by(Course.order).all()
    form.course.choices = [(c.name, c.name) for c in active_courses]

    if form.validate_on_submit():
        try:
            # Save PDF file
            pdf_file = form.pdf_file.data
            filename = secure_filename(pdf_file.filename)
            upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads/pdfs')

            # Ensure upload folder exists
            os.makedirs(upload_folder, exist_ok=True)

            # Save file
            filepath = os.path.join(upload_folder, filename)
            pdf_file.save(filepath)

            # Create book record
            book = Book(
                title=form.title.data,
                course=form.course.data,
                subject=form.subject.data,
                pdf_path=filepath,
                processed=False
            )
            db.session.add(book)
            db.session.commit()

            flash(f'Libro "{book.title}" subido exitosamente. Procesando...', 'success')

            # Process PDF in background (for now, do it synchronously)
            try:
                process_book_pdf(book.id)
                flash('Libro procesado y temas extraídos correctamente', 'success')
            except Exception as e:
                flash(f'Error al procesar el PDF: {str(e)}', 'warning')

            return redirect(url_for('admin.books'))

        except Exception as e:
            flash(f'Error al subir el libro: {str(e)}', 'error')
            db.session.rollback()

    return render_template('admin/upload_book.html', form=form)


def process_book_pdf(book_id: int):
    """Process PDF: extract text, generate embeddings, extract topics"""
    book = Book.query.get(book_id)
    if not book:
        return

    # Initialize services
    # Use larger chunk size (3000) for better topic extraction - allows ~30k chars total
    pdf_processor = PDFProcessor(chunk_size=3000, chunk_overlap=200)
    rag_service = RAGService()
    ai_engine = AIEngineFactory.create()

    # Extract and chunk text
    print(f"[DEBUG] Procesando PDF: {book.pdf_path}", flush=True)
    sys.stdout.flush()
    chunks = pdf_processor.process_pdf(book.pdf_path)
    print(f"[DEBUG] Chunks extraídos: {len(chunks)}", flush=True)
    sys.stdout.flush()

    # Store embeddings
    rag_service.store_chunks(book.id, chunks)
    print(f"[DEBUG] Embeddings almacenados", flush=True)
    sys.stdout.flush()

    # Extract topics using AI
    text_chunks = [chunk['text'] for chunk in chunks]
    book_metadata = {
        'title': book.title,
        'course': book.course,
        'subject': book.subject
    }

    print(f"[DEBUG] Llamando a extract_topics con {len(text_chunks)} chunks", flush=True)
    print(f"[DEBUG] Metadata: {book_metadata}", flush=True)
    sys.stdout.flush()

    topics_data = ai_engine.extract_topics(text_chunks, book_metadata)

    print(f"[DEBUG] ===== RESPUESTA CRUDA DE LA IA =====", flush=True)
    print(f"[DEBUG] Tipo: {type(topics_data)}", flush=True)
    print(f"[DEBUG] Contenido: {topics_data}", flush=True)
    print(f"[DEBUG] Longitud: {len(topics_data) if isinstance(topics_data, (list, dict)) else 'N/A'}", flush=True)
    print(f"[DEBUG] =====================================", flush=True)
    sys.stdout.flush()

    # Store topics
    for idx, topic_data in enumerate(topics_data):
        print(f"[DEBUG] Procesando tema {idx}: {topic_data}", flush=True)
        sys.stdout.flush()
        topic = Topic(
            book_id=book.id,
            topic_name=topic_data.get('name', 'Sin nombre'),
            description=topic_data.get('description', ''),
            order=idx
        )
        db.session.add(topic)

    print(f"[DEBUG] Total de temas guardados: {len(topics_data)}", flush=True)
    sys.stdout.flush()

    # Mark as processed
    book.processed = True
    db.session.commit()


@admin_bp.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_book(book_id):
    """Edit book metadata"""
    book = Book.query.get_or_404(book_id)
    form = EditBookForm(obj=book)

    # Populate course choices from database
    active_courses = Course.query.filter_by(active=True).order_by(Course.order).all()
    form.course.choices = [(c.name, c.name) for c in active_courses]

    if form.validate_on_submit():
        try:
            book.title = form.title.data
            book.course = form.course.data
            book.subject = form.subject.data
            db.session.commit()
            flash(f'Libro "{book.title}" actualizado correctamente', 'success')
            return redirect(url_for('admin.books'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el libro: {str(e)}', 'error')

    return render_template('admin/edit_book.html', form=form, book=book)


@admin_bp.route('/books/<int:book_id>/delete', methods=['POST'])
@admin_required
def delete_book(book_id):
    """Delete a book and all related data"""
    try:
        book = Book.query.get_or_404(book_id)

        # Delete PDF file from filesystem
        if os.path.exists(book.pdf_path):
            os.remove(book.pdf_path)

        # Delete book from database (cascade will handle topics, embeddings, exercises)
        db.session.delete(book)
        db.session.commit()

        flash(f'Libro "{book.title}" eliminado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el libro: {str(e)}', 'error')

    return redirect(url_for('admin.books'))


@admin_bp.route('/content')
@admin_required
def content():
    """Unified content management - PDFs and YouTube channels"""
    all_books = Book.query.order_by(Book.uploaded_at.desc()).all()
    all_channels = YouTubeChannel.query.order_by(YouTubeChannel.uploaded_at.desc()).all()

    return render_template('admin/content.html',
                         books=all_books,
                         channels=all_channels)


@admin_bp.route('/content/upload-youtube', methods=['GET', 'POST'])
@admin_required
def upload_youtube():
    """Add a new YouTube channel"""
    form = AddYouTubeChannelForm()

    # Populate course choices from database
    active_courses = Course.query.filter_by(active=True).order_by(Course.order).all()
    form.course.choices = [(c.name, c.name) for c in active_courses]

    if form.validate_on_submit():
        try:
            # Extract channel information
            channel_info = YouTubeService.extract_channel_info(form.channel_url.data)

            # Check if channel already exists
            existing_channel = YouTubeChannel.query.filter_by(
                channel_id=channel_info['channel_id']
            ).first()

            if existing_channel:
                flash(f'El canal "{channel_info["channel_name"]}" ya está agregado', 'warning')
                return redirect(url_for('admin.content'))

            # Get selected videos from hidden field
            selected_videos_json = request.form.get('selected_videos', '[]')
            try:
                selected_video_ids = json.loads(selected_videos_json)
            except json.JSONDecodeError:
                selected_video_ids = []

            # Validate that at least one video is selected
            if not selected_video_ids:
                flash('Debe seleccionar al menos un video para importar', 'error')
                return render_template('admin/upload_youtube.html', form=form)

            # Create channel record
            channel = YouTubeChannel(
                channel_url=form.channel_url.data,
                channel_id=channel_info['channel_id'],
                channel_name=channel_info['channel_name'],
                description=channel_info.get('description', ''),
                course=form.course.data,
                subject=form.subject.data,
                processed=False
            )
            db.session.add(channel)
            db.session.commit()

            flash(f'Canal "{channel.channel_name}" agregado exitosamente. Procesando {len(selected_video_ids)} videos...', 'success')

            # Process selected videos
            try:
                stats = YouTubeService.process_selected_videos(channel.id, selected_video_ids)

                flash(f'Canal procesado: {stats["videos_processed"]} videos procesados, '
                      f'{stats["videos_skipped"]} sin transcripción o ya existentes, '
                      f'{stats["topics_created"]} temas creados', 'success')

            except Exception as e:
                flash(f'Error al procesar el canal: {str(e)}', 'warning')

            return redirect(url_for('admin.content'))

        except Exception as e:
            flash(f'Error al agregar el canal: {str(e)}', 'error')
            db.session.rollback()

    return render_template('admin/upload_youtube.html', form=form)


@admin_bp.route('/content/youtube/fetch-videos', methods=['POST'])
@admin_required
def fetch_youtube_videos():
    """AJAX endpoint to fetch videos from a YouTube channel"""
    try:
        channel_url = request.json.get('channel_url')

        if not channel_url:
            return jsonify({'error': 'URL del canal requerida'}), 400

        # Extract channel information
        channel_info = YouTubeService.extract_channel_info(channel_url)

        # Get all videos from the channel
        videos = YouTubeService.get_channel_videos(channel_url)

        # Format video data for frontend
        videos_data = []
        for video in videos:
            # Format duration
            duration_minutes = video['duration'] // 60
            duration_seconds = video['duration'] % 60
            duration_str = f"{duration_minutes}:{duration_seconds:02d}"

            # Format date
            date_str = video['published_at'].strftime('%Y-%m-%d') if video['published_at'] else 'Desconocida'

            videos_data.append({
                'video_id': video['video_id'],
                'title': video['title'],
                'url': video['url'],
                'duration': duration_str,
                'published_at': date_str
            })

        return jsonify({
            'success': True,
            'channel_info': channel_info,
            'videos': videos_data,
            'total_videos': len(videos_data)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/content/youtube/<int:channel_id>/update', methods=['GET', 'POST'])
@admin_required
def update_youtube_channel(channel_id):
    """Update an existing YouTube channel with new videos"""
    channel = YouTubeChannel.query.get_or_404(channel_id)
    form = AddYouTubeChannelForm()

    # Populate course choices from database
    active_courses = Course.query.filter_by(active=True).order_by(Course.order).all()
    form.course.choices = [(c.name, c.name) for c in active_courses]

    # Pre-fill form with existing channel data
    if request.method == 'GET':
        form.channel_url.data = channel.channel_url
        form.course.data = channel.course
        form.subject.data = channel.subject

    if form.validate_on_submit():
        try:
            # Get selected videos from hidden field
            selected_videos_json = request.form.get('selected_videos', '[]')
            try:
                selected_video_ids = json.loads(selected_videos_json)
            except json.JSONDecodeError:
                selected_video_ids = []

            # Validate that at least one video is selected
            if not selected_video_ids:
                flash('Debe seleccionar al menos un video para importar', 'error')
                return render_template('admin/update_youtube.html', form=form, channel=channel)

            # Process selected videos (reuse existing logic)
            try:
                stats = YouTubeService.process_selected_videos(channel.id, selected_video_ids)

                flash(f'Canal actualizado: {stats["videos_processed"]} videos nuevos procesados, '
                      f'{stats["videos_skipped"]} omitidos, '
                      f'{stats["topics_created"]} temas creados', 'success')

            except Exception as e:
                flash(f'Error al actualizar el canal: {str(e)}', 'warning')

            return redirect(url_for('admin.content'))

        except Exception as e:
            flash(f'Error al actualizar el canal: {str(e)}', 'error')
            db.session.rollback()

    return render_template('admin/update_youtube.html', form=form, channel=channel)


@admin_bp.route('/content/youtube/<int:channel_id>/fetch-new-videos', methods=['POST'])
@admin_required
def fetch_new_youtube_videos(channel_id):
    """AJAX endpoint to fetch only new videos from an existing YouTube channel"""
    try:
        channel = YouTubeChannel.query.get_or_404(channel_id)

        # Get all videos from the channel
        all_videos = YouTubeService.get_channel_videos(channel.channel_url)

        # Get existing video IDs from database
        existing_video_ids = {v.video_id for v in channel.videos.all()}

        # Filter only new videos (not in database)
        new_videos = [v for v in all_videos if v['video_id'] not in existing_video_ids]

        # Format video data for frontend
        videos_data = []
        for video in new_videos:
            # Format duration
            duration_minutes = video['duration'] // 60
            duration_seconds = video['duration'] % 60
            duration_str = f"{duration_minutes}:{duration_seconds:02d}"

            # Format date
            date_str = video['published_at'].strftime('%Y-%m-%d') if video['published_at'] else 'Desconocida'

            videos_data.append({
                'video_id': video['video_id'],
                'title': video['title'],
                'url': video['url'],
                'duration': duration_str,
                'published_at': date_str
            })

        return jsonify({
            'success': True,
            'channel_info': {
                'channel_name': channel.channel_name,
                'channel_id': channel.channel_id
            },
            'videos': videos_data,
            'total_videos': len(videos_data),
            'existing_videos': len(existing_video_ids)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/content/youtube/<int:channel_id>/delete', methods=['POST'])
@admin_required
def delete_youtube_channel(channel_id):
    """Delete a YouTube channel and all related data"""
    try:
        channel = YouTubeChannel.query.get_or_404(channel_id)
        channel_name = channel.channel_name

        # Delete channel from database (cascade will handle videos, topics, embeddings)
        db.session.delete(channel)
        db.session.commit()

        flash(f'Canal "{channel_name}" eliminado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el canal: {str(e)}', 'error')

    return redirect(url_for('admin.content'))


@admin_bp.route('/ai-config')
@admin_required
def ai_config():
    """Configure AI engines"""
    import os
    active_engine = os.getenv('ACTIVE_AI_ENGINE', 'openai')
    active_model = os.getenv('ACTIVE_AI_MODEL', 'gpt-4')
    return render_template('admin/ai_config.html', active_engine=active_engine, active_model=active_model)


@admin_bp.route('/students')
@admin_required
def students():
    """Manage students and assign topics"""
    all_students = User.query.filter_by(role='student').all()
    return render_template('admin/students.html', students=all_students)


@admin_bp.route('/students/<int:student_id>/assign-topics', methods=['GET', 'POST'])
@admin_required
def assign_topics(student_id):
    """Assign topics to a student"""
    student = User.query.get_or_404(student_id)

    if request.method == 'POST':
        course = request.form.get('course')
        topic_ids = request.form.getlist('topics')

        # Create or update student profile
        profile = student.student_profile
        if not profile:
            profile = StudentProfile(user_id=student.id)
            db.session.add(profile)

        profile.course = course
        profile.set_topics([int(tid) for tid in topic_ids])

        db.session.commit()
        flash(f'Temas asignados correctamente a {student.username}', 'success')
        return redirect(url_for('admin.students'))

    # Get all topics grouped by source (books and YouTube channels)
    books = Book.query.filter_by(processed=True).all()
    channels = YouTubeChannel.query.filter_by(processed=True).all()

    return render_template('admin/assign_topics.html',
                         student=student,
                         books=books,
                         channels=channels)


@admin_bp.route('/students/create', methods=['GET', 'POST'])
@admin_required
def create_student():
    """Create a new student"""
    from app.models.student_score import StudentScore

    form = CreateStudentForm()

    # Populate course choices from database
    active_courses = Course.query.filter_by(active=True).order_by(Course.order).all()
    form.course.choices = [('', 'Seleccionar curso...')] + [(c.name, c.name) for c in active_courses]

    if form.validate_on_submit():
        try:
            # Check if username already exists
            if User.query.filter_by(username=form.username.data).first():
                flash('El nombre de usuario ya existe', 'error')
                return render_template('admin/create_student.html', form=form)

            # Check if email already exists (only if provided)
            if form.email.data and User.query.filter_by(email=form.email.data).first():
                flash('El email ya está registrado', 'error')
                return render_template('admin/create_student.html', form=form)

            # Create user
            student = User(
                username=form.username.data,
                email=form.email.data if form.email.data else None,
                centro=form.centro.data if form.centro.data else None,
                role='student'
            )
            student.set_password(form.password.data)
            db.session.add(student)
            db.session.flush()  # Get student ID

            # Create student profile
            profile = StudentProfile(
                user_id=student.id,
                course=form.course.data or ''
            )
            db.session.add(profile)

            # Create student score record
            score = StudentScore(
                student_id=student.id
            )
            db.session.add(score)

            db.session.commit()
            flash(f'Estudiante "{student.username}" creado exitosamente', 'success')
            return redirect(url_for('admin.students'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear estudiante: {str(e)}', 'error')

    return render_template('admin/create_student.html', form=form)


@admin_bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_student(student_id):
    """Edit student information"""
    student = User.query.get_or_404(student_id)

    if student.role != 'student':
        flash('Este usuario no es un estudiante', 'error')
        return redirect(url_for('admin.students'))

    form = EditStudentForm(obj=student)

    # Populate course choices from database
    active_courses = Course.query.filter_by(active=True).order_by(Course.order).all()
    form.course.choices = [('', 'Seleccionar curso...')] + [(c.name, c.name) for c in active_courses]

    # Pre-populate course and centro from profile
    if request.method == 'GET':
        if student.student_profile:
            form.course.data = student.student_profile.course
        if student.centro:
            form.centro.data = student.centro

    if form.validate_on_submit():
        try:
            # Check if username is taken by another user
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user and existing_user.id != student.id:
                flash('El nombre de usuario ya existe', 'error')
                return render_template('admin/edit_student.html', form=form, student=student)

            # Check if email is taken by another user (only if provided)
            if form.email.data:
                existing_email = User.query.filter_by(email=form.email.data).first()
                if existing_email and existing_email.id != student.id:
                    flash('El email ya está registrado', 'error')
                    return render_template('admin/edit_student.html', form=form, student=student)

            # Update user
            student.username = form.username.data
            student.email = form.email.data if form.email.data else None
            student.centro = form.centro.data if form.centro.data else None

            # Update password if provided
            if form.password.data:
                student.set_password(form.password.data)

            # Update or create profile
            if not student.student_profile:
                profile = StudentProfile(user_id=student.id)
                db.session.add(profile)
            else:
                profile = student.student_profile

            profile.course = form.course.data or ''

            db.session.commit()
            flash(f'Estudiante "{student.username}" actualizado correctamente', 'success')
            return redirect(url_for('admin.students'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar estudiante: {str(e)}', 'error')

    return render_template('admin/edit_student.html', form=form, student=student)


@admin_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@admin_required
def delete_student(student_id):
    """Delete a student"""
    try:
        student = User.query.get_or_404(student_id)

        if student.role != 'student':
            flash('Este usuario no es un estudiante', 'error')
            return redirect(url_for('admin.students'))

        username = student.username

        # Delete student (cascade will handle profile, scores, submissions)
        db.session.delete(student)
        db.session.commit()

        flash(f'Estudiante "{username}" eliminado correctamente', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar estudiante: {str(e)}', 'error')

    return redirect(url_for('admin.students'))


@admin_bp.route('/students/<int:student_id>/statistics')
@admin_required
def student_statistics(student_id):
    """View detailed statistics for a student"""
    from app.services.scoring_service import ScoringService
    from app.models.student_score import StudentScore
    from app.models.exercise import Exercise
    from app.models.submission import Submission

    student = User.query.get_or_404(student_id)

    if student.role != 'student':
        flash('Este usuario no es un estudiante', 'error')
        return redirect(url_for('admin.students'))

    # Get general statistics
    stats = ScoringService.get_student_statistics(student_id)

    # Get student profile info
    profile = StudentProfile.query.filter_by(user_id=student_id).first()

    # Get submission history (last 10)
    recent_submissions = Submission.query.filter_by(student_id=student_id)\
        .order_by(Submission.submitted_at.desc())\
        .limit(10)\
        .all()

    # Calculate additional stats
    total_submissions = Submission.query.filter_by(student_id=student_id).count()
    correct_submissions = Submission.query.filter_by(student_id=student_id, is_correct_result=True).count()

    # Get assigned topics
    assigned_topics = profile.get_topics() if profile else []

    return render_template('admin/student_statistics.html',
                         student=student,
                         stats=stats,
                         profile=profile,
                         recent_submissions=recent_submissions,
                         total_submissions=total_submissions,
                         correct_submissions=correct_submissions,
                         assigned_topics=assigned_topics)


@admin_bp.route('/student/<int:student_id>/exercise-history')
@admin_required
def exercise_history(student_id):
    """View complete exercise history for a student with filters and pagination"""
    student = User.query.get_or_404(student_id)

    if student.role != 'student':
        flash('Este usuario no es un estudiante.', 'error')
        return redirect(url_for('admin.students'))

    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    topic_id = request.args.get('topic_id', type=int)
    is_correct = request.args.get('is_correct', type=str)
    date_from = request.args.get('date_from', type=str)
    date_to = request.args.get('date_to', type=str)

    # Build filters dict
    filters = {}
    if topic_id:
        filters['topic_id'] = topic_id
    if is_correct == 'true':
        filters['is_correct'] = True
    elif is_correct == 'false':
        filters['is_correct'] = False
    if date_from:
        from datetime import datetime
        filters['date_from'] = datetime.strptime(date_from, '%Y-%m-%d')
    if date_to:
        from datetime import datetime
        filters['date_to'] = datetime.strptime(date_to, '%Y-%m-%d')

    # Get paginated history
    history = AnalyticsService.get_student_exercise_history(
        student_id=student_id,
        filters=filters,
        page=page,
        per_page=per_page
    )

    # Get all topics for filter dropdown
    profile = student.student_profile
    if profile:
        topic_ids = profile.get_topics()
        available_topics = Topic.query.filter(Topic.id.in_(topic_ids)).all() if topic_ids else []
    else:
        available_topics = []

    return render_template('admin/exercise_history.html',
                         student=student,
                         history=history,
                         available_topics=available_topics,
                         current_filters={
                             'topic_id': topic_id,
                             'is_correct': is_correct,
                             'date_from': date_from,
                             'date_to': date_to
                         })


@admin_bp.route('/student/<int:student_id>/topic-analytics')
@admin_required
def topic_analytics(student_id):
    """View topic-based performance analytics for a student"""
    student = User.query.get_or_404(student_id)

    if student.role != 'student':
        flash('Este usuario no es un estudiante.', 'error')
        return redirect(url_for('admin.students'))

    # Get topic performance data
    topic_performance = AnalyticsService.get_topic_performance(student_id)

    # Get weak topics
    weak_topics = AnalyticsService.calculate_weak_topics(student_id)

    # Get recommendations
    recommendations = AnalyticsService.get_recommendations(student_id)

    # Get time series data for chart
    time_series = AnalyticsService.get_time_series_data(student_id, days=30)

    return render_template('admin/topic_analytics.html',
                         student=student,
                         topic_performance=topic_performance,
                         weak_topics=weak_topics,
                         recommendations=recommendations,
                         time_series=time_series)


@admin_bp.route('/student/<int:student_id>/export-csv')
@admin_required
def export_student_csv(student_id):
    """Export student exercise history to CSV"""
    student = User.query.get_or_404(student_id)

    if student.role != 'student':
        flash('Este usuario no es un estudiante.', 'error')
        return redirect(url_for('admin.students'))

    # Generate CSV
    csv_data = AnalyticsService.export_to_csv(student_id)

    # Create response
    response = Response(csv_data, mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=student_{student.username}_history.csv'

    return response


@admin_bp.route('/admins')
@admin_required
def admins():
    """Manage administrators"""
    all_admins = User.query.filter_by(role='admin').all()
    return render_template('admin/admins.html', admins=all_admins)


@admin_bp.route('/admins/create', methods=['GET', 'POST'])
@admin_required
def create_admin():
    """Create a new administrator"""
    form = CreateAdminForm()

    if form.validate_on_submit():
        try:
            # Check if username already exists
            if User.query.filter_by(username=form.username.data).first():
                flash('El nombre de usuario ya existe', 'error')
                return render_template('admin/create_admin.html', form=form)

            # Check if email already exists (only if provided)
            if form.email.data and User.query.filter_by(email=form.email.data).first():
                flash('El email ya está registrado', 'error')
                return render_template('admin/create_admin.html', form=form)

            # Create user
            admin = User(
                username=form.username.data,
                email=form.email.data if form.email.data else None,
                centro=form.centro.data if form.centro.data else None,
                role='admin'
            )
            admin.set_password(form.password.data)
            db.session.add(admin)
            db.session.commit()

            flash(f'Administrador "{admin.username}" creado exitosamente', 'success')
            return redirect(url_for('admin.admins'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear administrador: {str(e)}', 'error')

    return render_template('admin/create_admin.html', form=form)


@admin_bp.route('/admins/<int:admin_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_admin(admin_id):
    """Edit administrator information"""
    admin_user = User.query.get_or_404(admin_id)

    if admin_user.role != 'admin':
        flash('Este usuario no es un administrador', 'error')
        return redirect(url_for('admin.admins'))

    # Prevent editing the current admin if it's the only admin
    admin_count = User.query.filter_by(role='admin').count()
    if admin_count == 1 and admin_user.id == current_user.id:
        flash('No puedes editar el único administrador del sistema', 'warning')
        return redirect(url_for('admin.admins'))

    form = EditAdminForm(obj=admin_user)

    # Pre-populate centro
    if request.method == 'GET' and admin_user.centro:
        form.centro.data = admin_user.centro

    if form.validate_on_submit():
        try:
            # Check if username is taken by another user
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user and existing_user.id != admin_user.id:
                flash('El nombre de usuario ya existe', 'error')
                return render_template('admin/edit_admin.html', form=form, admin=admin_user)

            # Check if email is taken by another user (only if provided)
            if form.email.data:
                existing_email = User.query.filter_by(email=form.email.data).first()
                if existing_email and existing_email.id != admin_user.id:
                    flash('El email ya está registrado', 'error')
                    return render_template('admin/edit_admin.html', form=form, admin=admin_user)

            # Update user
            admin_user.username = form.username.data
            admin_user.email = form.email.data if form.email.data else None
            admin_user.centro = form.centro.data if form.centro.data else None

            # Update password if provided
            if form.password.data:
                admin_user.set_password(form.password.data)

            db.session.commit()
            flash(f'Administrador "{admin_user.username}" actualizado correctamente', 'success')
            return redirect(url_for('admin.admins'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar administrador: {str(e)}', 'error')

    return render_template('admin/edit_admin.html', form=form, admin=admin_user)


@admin_bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@admin_required
def delete_admin(admin_id):
    """Delete an administrator"""
    try:
        admin_user = User.query.get_or_404(admin_id)

        if admin_user.role != 'admin':
            flash('Este usuario no es un administrador', 'error')
            return redirect(url_for('admin.admins'))

        # Prevent deleting yourself
        if admin_user.id == current_user.id:
            flash('No puedes eliminarte a ti mismo', 'error')
            return redirect(url_for('admin.admins'))

        # Prevent deleting the last admin
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count == 1:
            flash('No puedes eliminar el único administrador del sistema', 'error')
            return redirect(url_for('admin.admins'))

        username = admin_user.username

        # Delete admin
        db.session.delete(admin_user)
        db.session.commit()

        flash(f'Administrador "{username}" eliminado correctamente', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar administrador: {str(e)}', 'error')

    return redirect(url_for('admin.admins'))


@admin_bp.route('/backups')
@admin_required
def backups():
    """Manage backups"""
    try:
        all_backups = BackupService.list_backups()
        return render_template('admin/backups.html', backups=all_backups)
    except Exception as e:
        flash(f'Error al listar backups: {str(e)}', 'error')
        return render_template('admin/backups.html', backups=[])


@admin_bp.route('/backups/create', methods=['POST'])
@admin_required
def create_backup():
    """Create a new backup"""
    try:
        backup_info = BackupService.create_backup()
        flash(f'Backup creado exitosamente: {backup_info["filename"]} ({backup_info["size_mb"]} MB)', 'success')
    except Exception as e:
        flash(f'Error al crear backup: {str(e)}', 'error')

    return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/upload', methods=['POST'])
@admin_required
def upload_backup():
    """Upload a backup file"""
    try:
        # Check if file was uploaded
        if 'backup_file' not in request.files:
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(url_for('admin.backups'))

        file = request.files['backup_file']

        # Check if file has a filename
        if file.filename == '':
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(url_for('admin.backups'))

        # Upload and validate backup
        backup_info = BackupService.upload_backup(file)
        flash(f'Backup subido exitosamente: {backup_info["filename"]} ({backup_info["size_mb"]} MB)', 'success')

    except Exception as e:
        flash(f'Error al subir backup: {str(e)}', 'error')

    return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/<filename>/download')
@admin_required
def download_backup(filename):
    """Download a backup file"""
    try:
        filepath = BackupService.get_backup_path(filename)

        if not filepath:
            flash('Backup no encontrado', 'error')
            return redirect(url_for('admin.backups'))

        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/gzip'
        )
    except Exception as e:
        flash(f'Error al descargar backup: {str(e)}', 'error')
        return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/<filename>/delete', methods=['POST'])
@admin_required
def delete_backup(filename):
    """Delete a backup file"""
    try:
        if BackupService.delete_backup(filename):
            flash(f'Backup "{filename}" eliminado correctamente', 'success')
        else:
            flash('No se pudo eliminar el backup', 'error')
    except Exception as e:
        flash(f'Error al eliminar backup: {str(e)}', 'error')

    return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/<filename>/restore', methods=['POST'])
@admin_required
def restore_backup(filename):
    """Restore from a backup file"""
    try:
        # Add confirmation check
        confirm = request.form.get('confirm')
        if confirm != 'RESTAURAR':
            flash('Debes escribir "RESTAURAR" para confirmar la restauración', 'error')
            return redirect(url_for('admin.backups'))

        # Close all SQLAlchemy connections before restore
        db.session.remove()
        db.engine.dispose()

        result = BackupService.restore_backup(filename)

        # The database connection will be lost during restore, so we need to redirect
        # to login page as the session will be invalidated
        flash('Backup restaurado exitosamente. Por favor, vuelve a iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    except Exception as e:
        flash(f'Error al restaurar backup: {str(e)}', 'error')
        return redirect(url_for('admin.backups'))


# ==================== COURSE MANAGEMENT ====================

@admin_bp.route('/courses')
@admin_required
def courses():
    """Manage courses"""
    all_courses = Course.query.order_by(Course.order).all()
    return render_template('admin/courses.html', courses=all_courses)


@admin_bp.route('/courses/create', methods=['GET', 'POST'])
@admin_required
def create_course():
    """Create a new course"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            order = request.form.get('order', type=int)

            if not name:
                flash('El nombre del curso es obligatorio', 'error')
                return redirect(url_for('admin.courses'))

            # Check if course already exists
            if Course.query.filter_by(name=name).first():
                flash('Ya existe un curso con ese nombre', 'error')
                return redirect(url_for('admin.courses'))

            # If order not provided, use the next available number
            if order is None:
                max_order = db.session.query(db.func.max(Course.order)).scalar() or 0
                order = max_order + 1

            course = Course(name=name, order=order)
            db.session.add(course)
            db.session.commit()

            flash(f'Curso "{name}" creado exitosamente', 'success')
            return redirect(url_for('admin.courses'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear curso: {str(e)}', 'error')
            return redirect(url_for('admin.courses'))

    # GET request - get next order number
    max_order = db.session.query(db.func.max(Course.order)).scalar() or 0
    next_order = max_order + 1
    return render_template('admin/create_course.html', next_order=next_order)


@admin_bp.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_course(course_id):
    """Edit a course"""
    course = Course.query.get_or_404(course_id)

    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            order = request.form.get('order', type=int)
            active = request.form.get('active') == 'on'

            if not name:
                flash('El nombre del curso es obligatorio', 'error')
                return render_template('admin/edit_course.html', course=course)

            # Check if another course has the same name
            existing = Course.query.filter_by(name=name).filter(Course.id != course_id).first()
            if existing:
                flash('Ya existe otro curso con ese nombre', 'error')
                return render_template('admin/edit_course.html', course=course)

            course.name = name
            if order is not None:
                course.order = order
            course.active = active

            db.session.commit()
            flash(f'Curso "{name}" actualizado exitosamente', 'success')
            return redirect(url_for('admin.courses'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar curso: {str(e)}', 'error')

    return render_template('admin/edit_course.html', course=course)


@admin_bp.route('/courses/<int:course_id>/delete', methods=['POST'])
@admin_required
def delete_course(course_id):
    """Delete a course"""
    try:
        course = Course.query.get_or_404(course_id)
        course_name = course.name

        # Check if course is being used by students or books
        students_using = StudentProfile.query.filter_by(course=course_name).count()
        books_using = Book.query.filter_by(course=course_name).count()

        if students_using > 0 or books_using > 0:
            flash(f'No se puede eliminar el curso "{course_name}" porque está siendo utilizado por {students_using} estudiante(s) y {books_using} libro(s)', 'error')
            return redirect(url_for('admin.courses'))

        db.session.delete(course)
        db.session.commit()
        flash(f'Curso "{course_name}" eliminado exitosamente', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar curso: {str(e)}', 'error')

    return redirect(url_for('admin.courses'))
