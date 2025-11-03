"""
Admin routes
"""
import os
import sys
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.admin import admin_bp
from app.admin.forms import UploadBookForm, EditBookForm, CreateStudentForm, EditStudentForm
from app import db
from app.models.book import Book
from app.models.topic import Topic
from app.models.user import User
from app.models.student_profile import StudentProfile
from app.services.pdf_processor import PDFProcessor
from app.services.rag_service import RAGService
from app.ai_engines.factory import AIEngineFactory


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
    students_count = User.query.filter_by(role='student').count()
    topics_count = Topic.query.count()

    return render_template('admin/dashboard.html',
                         books_count=books_count,
                         students_count=students_count,
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


@admin_bp.route('/ai-config')
@admin_required
def ai_config():
    """Configure AI engines"""
    return render_template('admin/ai_config.html')


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

    # Get all topics grouped by book
    books = Book.query.filter_by(processed=True).all()

    return render_template('admin/assign_topics.html',
                         student=student,
                         books=books)


@admin_bp.route('/students/create', methods=['GET', 'POST'])
@admin_required
def create_student():
    """Create a new student"""
    from app.models.student_score import StudentScore

    form = CreateStudentForm()

    if form.validate_on_submit():
        try:
            # Check if username already exists
            if User.query.filter_by(username=form.username.data).first():
                flash('El nombre de usuario ya existe', 'error')
                return render_template('admin/create_student.html', form=form)

            # Check if email already exists
            if User.query.filter_by(email=form.email.data).first():
                flash('El email ya está registrado', 'error')
                return render_template('admin/create_student.html', form=form)

            # Create user
            student = User(
                username=form.username.data,
                email=form.email.data,
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

    # Pre-populate course from profile
    if request.method == 'GET' and student.student_profile:
        form.course.data = student.student_profile.course

    if form.validate_on_submit():
        try:
            # Check if username is taken by another user
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user and existing_user.id != student.id:
                flash('El nombre de usuario ya existe', 'error')
                return render_template('admin/edit_student.html', form=form, student=student)

            # Check if email is taken by another user
            existing_email = User.query.filter_by(email=form.email.data).first()
            if existing_email and existing_email.id != student.id:
                flash('El email ya está registrado', 'error')
                return render_template('admin/edit_student.html', form=form, student=student)

            # Update user
            student.username = form.username.data
            student.email = form.email.data

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
