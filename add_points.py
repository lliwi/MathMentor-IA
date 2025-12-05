"""
Script to add points to a student account
Usage: python add_points.py <username> <points>
Example: python add_points.py maria 100
"""
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.user import User
from app.models.student_score import StudentScore


def add_points(username, points):
    """Add points to a student's account"""
    app = create_app()

    with app.app_context():
        # Find user
        user = User.query.filter_by(username=username).first()

        if not user:
            print(f"❌ Error: Usuario '{username}' no encontrado")
            return False

        if user.role != 'student':
            print(f"❌ Error: El usuario '{username}' no es un estudiante (role={user.role})")
            return False

        # Get or create student score
        student_score = StudentScore.query.filter_by(student_id=user.id).first()

        if not student_score:
            print(f"Creando registro de puntuación para '{username}'...")
            student_score = StudentScore(student_id=user.id)
            db.session.add(student_score)
            db.session.flush()

        # Show current points
        print(f"\n📊 Estado actual de '{username}':")
        print(f"   Total de puntos ganados: {student_score.total_points}")
        print(f"   Puntos disponibles: {student_score.available_points}")
        print(f"   Puntos gastados: {student_score.points_spent}")

        # Add points
        student_score.add_points(points)
        db.session.commit()

        # Show updated points
        print(f"\n✅ Se agregaron {points} puntos exitosamente!")
        print(f"\n📊 Estado actualizado:")
        print(f"   Total de puntos ganados: {student_score.total_points}")
        print(f"   Puntos disponibles: {student_score.available_points}")
        print(f"   Puntos gastados: {student_score.points_spent}")

        return True


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Uso: python add_points.py <username> <points>")
        print("Ejemplo: python add_points.py maria 100")
        sys.exit(1)

    username = sys.argv[1]
    try:
        points = int(sys.argv[2])
    except ValueError:
        print("❌ Error: Los puntos deben ser un número entero")
        sys.exit(1)

    if points <= 0:
        print("❌ Error: Los puntos deben ser mayores que 0")
        sys.exit(1)

    success = add_points(username, points)
    sys.exit(0 if success else 1)
