"""
Script to add performance indexes to the database

Run this after database initialization to optimize query performance.
This is idempotent - safe to run multiple times.
"""
from app import create_app, db
from sqlalchemy import text

def add_performance_indexes():
    """Add indexes for better query performance"""
    app = create_app()

    with app.app_context():
        try:
            print("\n" + "="*60)
            print("🔧 Adding Performance Indexes")
            print("="*60 + "\n")

            # Get embedding dimension from existing data
            result = db.session.execute(text("""
                SELECT embedding FROM document_embeddings LIMIT 1
            """)).fetchone()

            if result:
                # HNSW index for pgvector (faster than IVFFlat for most use cases)
                print("📊 Creating HNSW index for vector similarity search...")
                print("   (This may take a few minutes for large datasets)")
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw
                    ON document_embeddings
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64)
                """))
                print("   ✅ HNSW index created")
            else:
                print("   ⚠️  No embeddings found, skipping HNSW index")

            # Composite indexes for common queries
            print("\n📊 Creating composite indexes...")

            indexes = [
                ("idx_embeddings_book_page", "document_embeddings", "(book_id, page_number)"),
                ("idx_embeddings_book_id", "document_embeddings", "(book_id)"),
                ("idx_exercises_topic", "exercises", "(topic_id, generated_at DESC)"),
                ("idx_submissions_student", "submissions", "(student_id, submitted_at DESC)"),
                ("idx_submissions_exercise", "submissions", "(exercise_id, submitted_at DESC)"),
                ("idx_submissions_student_exercise", "submissions", "(student_id, exercise_id)"),
                ("idx_topics_book", "topics", "(book_id)"),
            ]

            for idx_name, table_name, columns in indexes:
                try:
                    db.session.execute(text(f"""
                        CREATE INDEX IF NOT EXISTS {idx_name}
                        ON {table_name} {columns}
                    """))
                    db.session.commit()  # Commit each index individually
                    print(f"   ✅ {idx_name} created on {table_name}")
                except Exception as e:
                    db.session.rollback()  # Rollback on error
                    print(f"   ⚠️  {idx_name}: {str(e)}")

            db.session.commit()

            print("\n" + "="*60)
            print("✅ Performance indexes added successfully!")
            print("="*60)

            # Show index information
            print("\n📊 Index Statistics:")
            result = db.session.execute(text("""
                SELECT
                    schemaname,
                    tablename,
                    indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND (
                    indexname LIKE 'idx_embeddings_%'
                    OR indexname LIKE 'idx_exercises_%'
                    OR indexname LIKE 'idx_submissions_%'
                    OR indexname LIKE 'idx_topics_%'
                )
                ORDER BY tablename, indexname
            """))

            for row in result:
                print(f"   ✅ {row[1]}.{row[2]}")

            print("\n" + "="*60 + "\n")

        except Exception as e:
            print(f"\n❌ Error adding indexes: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    add_performance_indexes()
