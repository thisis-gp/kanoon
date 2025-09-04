from database_manager import DatabaseManager

def migrate_existing_database():
    """Migrate existing database to enhanced version"""
    try:
        print("🚀 Starting database migration...")
        DatabaseManager.create_enhanced_tables()
        print("✅ Database migration completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate_existing_database()