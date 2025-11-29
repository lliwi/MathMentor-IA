"""
Initialize database and create test users
"""
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.user import User
from app.models.student_profile import StudentProfile
from app.models.student_score import StudentScore
from app.models.course import Course
from app.services.rag_service import RAGService


def init_database():
    """Initialize database and create tables"""
    app = create_app()

    with app.app_context():
        # Initialize pgvector extension FIRST
        print("Initializing pgvector extension...")
        rag_service = RAGService()
        rag_service.initialize_pgvector()

        # Drop all tables and recreate (CAUTION: This deletes all data!)
        print("Creating database tables...")
        db.create_all()

        # Create admin user (has access to all features including exercise management)
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Creating admin user...")
            admin = User(
                username='admin',
                email='admin@mathmentor.com',
                role='admin'
            )
            admin.set_password('admin123')  # Change this in production!
            db.session.add(admin)

        # Create default courses
        default_courses = [
            ('1º ESO', 1),
            ('2º ESO', 2),
            ('3º ESO', 3),
            ('4º ESO', 4),
            ('1º Bachillerato', 5),
            ('2º Bachillerato', 6),
        ]

        for course_name, order in default_courses:
            course = Course.query.filter_by(name=course_name).first()
            if not course:
                print(f"Creating course: {course_name}...")
                course = Course(name=course_name, order=order, active=True)
                db.session.add(course)

        # Create test student users
        students = [
            ('maria', 'maria@estudiante.com', '1º ESO'),
            ('juan', 'juan@estudiante.com', '2º ESO'),
            ('lucia', 'lucia@estudiante.com', '3º ESO'),
        ]

        for username, email, course in students:
            student = User.query.filter_by(username=username).first()
            if not student:
                print(f"Creating student: {username}...")
                student = User(
                    username=username,
                    email=email,
                    role='student'
                )
                student.set_password('estudiante123')  # Change this in production!
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
        print("\nDatabase initialized successfully!")
        print("\nTest users created:")
        print("Admin: username='admin', password='admin123' (includes exercise management)")
        print("Students: username='maria/juan/lucia', password='estudiante123'")
        print("\nIMPORTANT: Change these passwords in production!")


if __name__ == '__main__':
    init_database()
