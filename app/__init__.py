"""
MathMentor IA - Application Factory
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_name=None):
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Aumentado a 1GB para permitir backups grandes
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_SIZE', 1073741824))  # 1 GB por defecto
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads/pdfs')

    # Database connection pooling for better performance
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,              # Number of connections to keep open
        'pool_recycle': 3600,          # Recycle connections after 1 hour
        'pool_pre_ping': True,         # Test connections before using
        'max_overflow': 20,            # Extra connections beyond pool_size
        'pool_timeout': 30             # Timeout for getting connection from pool
    }

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'

    # Auto-initialize database on first run
    with app.app_context():
        _auto_initialize_database()

    # Register blueprints
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.student import student_bp
    from app.teacher import teacher_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')

    # Jinja filter: quita la sintaxis Markdown/LaTeX para previsualizaciones en texto plano
    import re as _re

    @app.template_filter('strip_md')
    def strip_md(text):
        if not text:
            return ''
        s = str(text)
        s = _re.sub(r'`{1,3}', '', s)              # code / code spans
        s = _re.sub(r'\*\*|\*|__|_|~~', '', s)      # bold / italic / strikethrough
        s = _re.sub(r'^\s{0,3}#{1,6}\s*', '', s, flags=_re.MULTILINE)  # headings
        s = _re.sub(r'^\s{0,3}>\s?', '', s, flags=_re.MULTILINE)       # blockquotes
        s = _re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', s)             # links / images
        s = _re.sub(r'\${1,2}', '', s)             # LaTeX $ / $$ delimiters
        s = _re.sub(r'\s+', ' ', s)                # colapsa espacios y saltos
        return s.strip()

    # Home route
    @app.route('/')
    def index():
        from flask import redirect, url_for, render_template
        from flask_login import current_user

        if current_user.is_authenticated:
            if current_user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif current_user.role == 'teacher':
                return redirect(url_for('teacher.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        return render_template('landing/index.html')

    return app


def _auto_initialize_database():
    """Auto-initialize database if it's a fresh installation"""
    try:
        from app.models.user import User
        from app.models.student_profile import StudentProfile
        from app.models.student_score import StudentScore
        from app.models.youtube_channel import YouTubeChannel
        from app.models.youtube_video import YouTubeVideo
        from app.models.video_embedding import VideoEmbedding
        from app.services.rag_service import RAGService
        from sqlalchemy import inspect

        # Check if users table exists
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        if 'users' not in tables:
            # Fresh installation - initialize everything
            print("\n" + "="*60)
            print("🚀 NEW INSTALLATION DETECTED - Auto-initializing database...")
            print("="*60)

            # Initialize pgvector extension FIRST (before creating tables)
            print("📦 Initializing pgvector extension...")
            rag_service = RAGService()
            rag_service.initialize_pgvector()

            # Create all tables
            print("🗄️  Creating database tables...")
            db.create_all()

            # Create admin user (includes exercise management capabilities)
            print("👤 Creating admin user...")
            admin = User(
                username='admin',
                email='admin@mathmentor.com',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)

            # Create test student users
            students = [
                ('maria', 'maria@estudiante.com', '1º ESO'),
                ('juan', 'juan@estudiante.com', '2º ESO'),
                ('lucia', 'lucia@estudiante.com', '3º ESO'),
            ]

            for username, email, course in students:
                print(f"👨‍🎓 Creating student: {username}...")
                student = User(
                    username=username,
                    email=email,
                    role='student'
                )
                student.set_password('estudiante123')
                db.session.add(student)
                db.session.flush()  # Get student ID

                # Create student profile
                profile = StudentProfile(
                    user_id=student.id,
                    course=course
                )
                db.session.add(profile)

                # Create student score record
                score = StudentScore(
                    student_id=student.id
                )
                db.session.add(score)

            db.session.commit()

            print("\n" + "="*60)
            print("✅ Database initialized successfully!")
            print("="*60)
            print("\n📋 Test users created:")
            print("   Admin: username='admin', password='admin123' (includes exercise management)")
            print("   Students: username='maria/juan/lucia', password='estudiante123'")
            print("\n⚠️  IMPORTANT: Change these passwords in production!")
            print("="*60 + "\n")
        else:
            # Tables exist, check if users exist
            user_count = User.query.count()
            if user_count == 0:
                # Tables exist but no users - create test users only
                print("📋 Creating test users...")

                admin = User(
                    username='admin',
                    email='admin@mathmentor.com',
                    role='admin'
                )
                admin.set_password('admin123')
                db.session.add(admin)

                students = [
                    ('maria', 'maria@estudiante.com', '1º ESO'),
                    ('juan', 'juan@estudiante.com', '2º ESO'),
                    ('lucia', 'lucia@estudiante.com', '3º ESO'),
                ]

                for username, email, course in students:
                    student = User(
                        username=username,
                        email=email,
                        role='student'
                    )
                    student.set_password('estudiante123')
                    db.session.add(student)
                    db.session.flush()

                    profile = StudentProfile(user_id=student.id, course=course)
                    db.session.add(profile)

                    score = StudentScore(student_id=student.id)
                    db.session.add(score)

                db.session.commit()
                print("✅ Test users created!")

    except Exception as e:
        print(f"⚠️  Auto-initialization skipped: {str(e)}")


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    from app.models.user import User
    return User.query.get(int(user_id))
