try:
    from .insert_metadata import insert_metadata
    print("✅ Imported insert_metadata")
except ImportError as e:
    print(f"⚠️ Could not import insert_metadata: {e}")
    insert_metadata = None

try:
    from .query_metadata import search_cases_by_judge, show_all_cases
    print("✅ Imported query functions")
except ImportError as e:
    print(f"⚠️ Could not import query functions: {e}")
    search_cases_by_judge = None
    show_all_cases = None

try:
    from .create_metadata_table import create_db
    print("✅ Imported create_db")
except ImportError as e:
    print(f"⚠️ Could not import create_db: {e}")
    create_db = None

try:
    from .database_manager import DatabaseManager, get_db_connection
    # Initialize database on import
    DatabaseManager.create_enhanced_tables()
    print("✅ Database initialized successfully")
except ImportError as e:
    print(f"❌ Could not import DatabaseManager: {e}")
    DatabaseManager = None
    get_db_connection = None
except Exception as e:
    print(f"❌ Error initializing database: {e}")

__all__ = [
    'insert_metadata',
    'search_cases_by_judge', 
    'show_all_cases',
    'create_db',
    'DatabaseManager',
    'get_db_connection'
]