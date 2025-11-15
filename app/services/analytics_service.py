"""
Analytics Service - Provides advanced student performance analytics
"""
from sqlalchemy import func, distinct, case
from app.models.submission import Submission
from app.models.exercise import Exercise
from app.models.topic import Topic
from app.models.user import User
from app import db
from datetime import datetime, timedelta
import json


class AnalyticsService:
    """Service for student performance analytics and reporting"""

    @staticmethod
    def get_student_exercise_history(student_id, filters=None, page=1, per_page=20):
        """
        Get paginated exercise history for a student with optional filters

        Args:
            student_id: Student user ID
            filters: Dict with optional keys: topic_id, is_correct, date_from, date_to
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Dict with 'items', 'total', 'pages', 'current_page'
        """
        # Base query with joins
        query = db.session.query(
            Submission,
            Exercise,
            Topic
        ).join(
            Exercise, Submission.exercise_id == Exercise.id
        ).join(
            Topic, Exercise.topic_id == Topic.id
        ).filter(
            Submission.student_id == student_id
        )

        # Apply filters
        if filters:
            if filters.get('topic_id'):
                query = query.filter(Exercise.topic_id == filters['topic_id'])

            if filters.get('is_correct') is not None:
                query = query.filter(Submission.is_correct_result == filters['is_correct'])

            if filters.get('date_from'):
                query = query.filter(Submission.submitted_at >= filters['date_from'])

            if filters.get('date_to'):
                query = query.filter(Submission.submitted_at <= filters['date_to'])

        # Order by most recent first
        query = query.order_by(Submission.submitted_at.desc())

        # Get total count
        total = query.count()

        # Calculate pagination
        offset = (page - 1) * per_page
        items_query = query.limit(per_page).offset(offset).all()

        # Calculate pages
        pages = (total + per_page - 1) // per_page if total > 0 else 1

        return {
            'items': [{
                'submission': submission,
                'exercise': exercise,
                'topic': topic
            } for submission, exercise, topic in items_query],
            'total': total,
            'pages': pages,
            'current_page': page,
            'has_prev': page > 1,
            'has_next': page < pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < pages else None
        }

    @staticmethod
    def get_completed_exercise_ids(student_id):
        """
        Get list of exercise IDs the student has already attempted
        Used for duplicate prevention

        Args:
            student_id: Student user ID

        Returns:
            List of exercise IDs
        """
        result = db.session.query(distinct(Submission.exercise_id)).filter(
            Submission.student_id == student_id
        ).all()

        return [row[0] for row in result]

    @staticmethod
    def get_completed_exercise_contents(student_id):
        """
        Get list of exercise contents the student has already completed
        Used for pool-based duplicate prevention

        Args:
            student_id: Student user ID

        Returns:
            List of exercise content strings
        """
        result = db.session.query(Exercise.content).join(
            Submission, Submission.exercise_id == Exercise.id
        ).filter(
            Submission.student_id == student_id
        ).distinct().all()

        return [row[0] for row in result]

    @staticmethod
    def get_topic_performance(student_id):
        """
        Get detailed performance metrics per topic

        Args:
            student_id: Student user ID

        Returns:
            List of dicts with topic performance data
        """
        # Query aggregated data per topic
        results = db.session.query(
            Topic.id,
            Topic.topic_name,
            func.count(Submission.id).label('total_attempts'),
            func.sum(case((Submission.is_correct_result == True, 1), else_=0)).label('correct_results'),
            func.sum(case((Submission.is_correct_methodology == True, 1), else_=0)).label('correct_methodology'),
            func.avg(Submission.total_score).label('avg_score'),
            func.count(distinct(Submission.exercise_id)).label('unique_exercises')
        ).join(
            Exercise, Topic.id == Exercise.topic_id
        ).join(
            Submission, Exercise.id == Submission.exercise_id
        ).filter(
            Submission.student_id == student_id
        ).group_by(
            Topic.id, Topic.topic_name
        ).all()

        topic_stats = []
        for row in results:
            topic_id, topic_name, total, correct_results, correct_methodology, avg_score, unique_exercises = row

            # Calculate percentages
            accuracy = (correct_results / total * 100) if total > 0 else 0
            methodology_rate = (correct_methodology / total * 100) if total > 0 else 0

            topic_stats.append({
                'topic_id': topic_id,
                'topic_name': topic_name,
                'total_attempts': total,
                'correct_results': correct_results,
                'correct_methodology': correct_methodology,
                'accuracy': round(accuracy, 1),
                'methodology_rate': round(methodology_rate, 1),
                'avg_score': round(avg_score, 1) if avg_score else 0,
                'unique_exercises': unique_exercises
            })

        # Sort by accuracy (weakest first)
        topic_stats.sort(key=lambda x: x['accuracy'])

        return topic_stats

    @staticmethod
    def calculate_weak_topics(student_id, accuracy_threshold=70, min_attempts=3):
        """
        Identify topics where student is struggling

        Args:
            student_id: Student user ID
            accuracy_threshold: Topics below this accuracy % are considered weak (default 70%)
            min_attempts: Minimum attempts needed to include topic (default 3)

        Returns:
            List of weak topic dicts with recommendations
        """
        topic_performance = AnalyticsService.get_topic_performance(student_id)

        weak_topics = [
            topic for topic in topic_performance
            if topic['accuracy'] < accuracy_threshold and topic['total_attempts'] >= min_attempts
        ]

        return weak_topics

    @staticmethod
    def get_recommendations(student_id):
        """
        Generate personalized recommendations for the student

        Args:
            student_id: Student user ID

        Returns:
            Dict with recommendations
        """
        weak_topics = AnalyticsService.calculate_weak_topics(student_id)
        topic_performance = AnalyticsService.get_topic_performance(student_id)

        recommendations = {
            'needs_practice': [],
            'doing_well': [],
            'needs_attention': []
        }

        for topic in topic_performance:
            if topic['accuracy'] < 50 and topic['total_attempts'] >= 3:
                recommendations['needs_attention'].append({
                    'topic': topic['topic_name'],
                    'accuracy': topic['accuracy'],
                    'message': f"Necesita atención urgente - {topic['accuracy']}% de aciertos"
                })
            elif topic['accuracy'] < 70 and topic['total_attempts'] >= 3:
                recommendations['needs_practice'].append({
                    'topic': topic['topic_name'],
                    'accuracy': topic['accuracy'],
                    'message': f"Requiere más práctica - {topic['accuracy']}% de aciertos"
                })
            elif topic['accuracy'] >= 80:
                recommendations['doing_well'].append({
                    'topic': topic['topic_name'],
                    'accuracy': topic['accuracy'],
                    'message': f"¡Excelente trabajo! - {topic['accuracy']}% de aciertos"
                })

        return recommendations

    @staticmethod
    def get_procedure_mistakes(student_id, limit=10):
        """
        Analyze which procedures students frequently select incorrectly

        Args:
            student_id: Student user ID
            limit: Number of top mistakes to return

        Returns:
            List of common procedure mistakes
        """
        # Get all incorrect methodology submissions
        submissions = db.session.query(Submission).filter(
            Submission.student_id == student_id,
            Submission.is_correct_methodology == False
        ).all()

        procedure_errors = {}

        for submission in submissions:
            if submission.selected_procedures and submission.exercise:
                selected = set(submission.selected_procedures)
                expected = set(submission.exercise.expected_procedures if submission.exercise.expected_procedures else [])

                # Find incorrect selections (selected but not expected)
                incorrect = selected - expected
                # Find missing selections (expected but not selected)
                missing = expected - selected

                # Count errors per procedure
                for proc_id in incorrect:
                    key = f"incorrect_{proc_id}"
                    if key not in procedure_errors:
                        procedure_errors[key] = {
                            'procedure_id': proc_id,
                            'type': 'incorrect_selection',
                            'count': 0
                        }
                    procedure_errors[key]['count'] += 1

                for proc_id in missing:
                    key = f"missing_{proc_id}"
                    if key not in procedure_errors:
                        procedure_errors[key] = {
                            'procedure_id': proc_id,
                            'type': 'missing_selection',
                            'count': 0
                        }
                    procedure_errors[key]['count'] += 1

        # Sort by frequency and return top mistakes
        sorted_errors = sorted(procedure_errors.values(), key=lambda x: x['count'], reverse=True)
        return sorted_errors[:limit]

    @staticmethod
    def export_to_csv(student_id):
        """
        Export student exercise history to CSV format

        Args:
            student_id: Student user ID

        Returns:
            CSV string
        """
        import csv
        from io import StringIO

        # Get all submissions
        history = AnalyticsService.get_student_exercise_history(
            student_id,
            page=1,
            per_page=10000  # Get all
        )

        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Fecha',
            'Tema',
            'Ejercicio',
            'Respuesta del Estudiante',
            'Resultado Correcto',
            'Metodología Correcta',
            'Puntos Resultado',
            'Puntos Metodología',
            'Puntos Esfuerzo',
            'Puntos Totales',
            'Es Reintento',
            'Retroalimentación'
        ])

        # Write data rows
        for item in history['items']:
            submission = item['submission']
            exercise = item['exercise']
            topic = item['topic']

            writer.writerow([
                submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                topic.topic_name,
                exercise.content[:100] + '...' if len(exercise.content) > 100 else exercise.content,
                submission.answer[:100] + '...' if len(submission.answer) > 100 else submission.answer,
                'Sí' if submission.is_correct_result else 'No',
                'Sí' if submission.is_correct_methodology else 'No',
                submission.score_result,
                submission.score_development,
                submission.score_effort,
                submission.total_score,
                'Sí' if submission.is_retry else 'No',
                submission.feedback[:200] + '...' if submission.feedback and len(submission.feedback) > 200 else submission.feedback
            ])

        return output.getvalue()

    @staticmethod
    def get_time_series_data(student_id, days=30):
        """
        Get performance data over time for charts

        Args:
            student_id: Student user ID
            days: Number of days to look back

        Returns:
            Dict with daily performance metrics
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get submissions grouped by date
        results = db.session.query(
            func.date(Submission.submitted_at).label('date'),
            func.count(Submission.id).label('total'),
            func.sum(case((Submission.is_correct_result == True, 1), else_=0)).label('correct'),
            func.avg(Submission.total_score).label('avg_score')
        ).filter(
            Submission.student_id == student_id,
            Submission.submitted_at >= cutoff_date
        ).group_by(
            func.date(Submission.submitted_at)
        ).order_by(
            func.date(Submission.submitted_at)
        ).all()

        time_series = []
        for row in results:
            date, total, correct, avg_score = row
            accuracy = (correct / total * 100) if total > 0 else 0

            time_series.append({
                'date': date.isoformat(),
                'total_exercises': total,
                'correct_exercises': correct,
                'accuracy': round(accuracy, 1),
                'avg_score': round(avg_score, 1) if avg_score else 0
            })

        return time_series
