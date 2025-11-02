"""
Scoring Service for gamification
"""
from datetime import datetime, timedelta
from app import db
from app.models.student_score import StudentScore
from app.models.submission import Submission


class ScoringService:
    """Service for managing student scores and gamification"""

    # Point values
    POINTS_CORRECT_RESULT = 10
    POINTS_CORRECT_METHODOLOGY = 5
    POINTS_EFFORT_RETRY = 3
    HINT_COST = 5

    # Streak bonus multipliers
    STREAK_BONUSES = {
        3: 2,   # 3 in a row: +2 points
        5: 5,   # 5 in a row: +5 points
        10: 10, # 10 in a row: +10 points
        15: 20  # 15 in a row: +20 points
    }

    @classmethod
    def calculate_score(cls, is_correct_result: bool, is_correct_methodology: bool,
                       is_retry: bool = False) -> dict:
        """
        Calculate points for a submission

        Args:
            is_correct_result: Whether the final answer is correct
            is_correct_methodology: Whether the methodology is correct
            is_retry: Whether this is a retry after feedback

        Returns:
            Dict with score breakdown
        """
        score_result = cls.POINTS_CORRECT_RESULT if is_correct_result else 0
        score_development = cls.POINTS_CORRECT_METHODOLOGY if is_correct_methodology else 0
        score_effort = cls.POINTS_EFFORT_RETRY if (is_retry and is_correct_result) else 0

        total_score = score_result + score_development + score_effort

        return {
            'score_result': score_result,
            'score_development': score_development,
            'score_effort': score_effort,
            'total_score': total_score
        }

    @classmethod
    def calculate_streak_bonus(cls, streak: int) -> int:
        """
        Calculate bonus points for streak

        Args:
            streak: Current streak count

        Returns:
            Bonus points
        """
        bonus = 0
        for threshold, points in cls.STREAK_BONUSES.items():
            if streak == threshold:
                bonus = points
                break
        return bonus

    @classmethod
    def update_student_score(cls, student_id: int, submission: Submission) -> dict:
        """
        Update student score after a submission

        Args:
            student_id: Student user ID
            submission: Submission instance

        Returns:
            Dict with updated score info and any bonuses
        """
        # Get or create student score record
        student_score = StudentScore.query.filter_by(student_id=student_id).first()

        if not student_score:
            student_score = StudentScore(student_id=student_id)
            db.session.add(student_score)

        # Add submission points
        student_score.add_points(submission.total_score)

        # Update exercise count
        student_score.total_exercises += 1
        if submission.is_correct_result:
            student_score.correct_exercises += 1

        # Update streak
        is_correct = submission.is_correct_result or submission.is_correct_methodology
        student_score.update_streak(is_correct)

        # Check for streak bonus
        streak_bonus = cls.calculate_streak_bonus(student_score.current_streak)
        if streak_bonus > 0:
            student_score.add_points(streak_bonus)

        db.session.commit()

        return {
            'total_points': student_score.total_points,
            'available_points': student_score.available_points,
            'current_streak': student_score.current_streak,
            'streak_bonus': streak_bonus,
            'best_streak': student_score.best_streak
        }

    @classmethod
    def purchase_hint(cls, student_id: int) -> tuple:
        """
        Purchase a hint using points

        Args:
            student_id: Student user ID

        Returns:
            Tuple (success: bool, message: str)
        """
        student_score = StudentScore.query.filter_by(student_id=student_id).first()

        if not student_score:
            return False, "No se encontró el registro de puntuación"

        if student_score.available_points < cls.HINT_COST:
            return False, f"Puntos insuficientes. Necesitas {cls.HINT_COST} puntos, tienes {student_score.available_points}"

        # Spend points
        if student_score.spend_points(cls.HINT_COST):
            db.session.commit()
            return True, f"Pista comprada. Puntos restantes: {student_score.available_points}"
        else:
            return False, "Error al procesar la compra"

    @classmethod
    def get_student_statistics(cls, student_id: int) -> dict:
        """
        Get comprehensive statistics for a student

        Args:
            student_id: Student user ID

        Returns:
            Dict with statistics
        """
        student_score = StudentScore.query.filter_by(student_id=student_id).first()

        if not student_score:
            return {
                'total_points': 0,
                'available_points': 0,
                'points_spent': 0,
                'current_streak': 0,
                'best_streak': 0,
                'total_exercises': 0,
                'correct_exercises': 0,
                'accuracy_rate': 0.0
            }

        accuracy_rate = 0.0
        if student_score.total_exercises > 0:
            accuracy_rate = (student_score.correct_exercises / student_score.total_exercises) * 100

        return {
            'total_points': student_score.total_points,
            'available_points': student_score.available_points,
            'points_spent': student_score.points_spent,
            'current_streak': student_score.current_streak,
            'best_streak': student_score.best_streak,
            'total_exercises': student_score.total_exercises,
            'correct_exercises': student_score.correct_exercises,
            'accuracy_rate': round(accuracy_rate, 2)
        }
