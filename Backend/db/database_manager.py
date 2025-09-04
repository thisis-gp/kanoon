import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Tuple

DATABASE_PATH = "cases_metadata.db"

@contextmanager
def get_db_connection():
    """Context manager for database connections with proper error handling"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()

class DatabaseManager:
    """Enhanced database operations manager"""
    
    @staticmethod
    def create_enhanced_tables():
        """Create tables with additional fields for FastAPI integration"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("PRAGMA table_info(case_metadata)")
                existing_columns = [row[1] for row in cursor.fetchall()]

                # Enhanced case_metadata table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS case_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    case_number TEXT,
                    petitioner TEXT,
                    respondent TEXT,
                    date TEXT,
                    judges TEXT,
                    acts_referred TEXT,
                    summary TEXT,
                    file_path TEXT,
                    content_hash TEXT,
                    vector_stored BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Add new columns if they don't exist
                new_columns = [
                    ("content_hash", "TEXT"),
                    ("vector_stored", "BOOLEAN DEFAULT FALSE"),
                    ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                    ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                ]
                
                for column_name, column_def in new_columns:
                        if column_name not in existing_columns:
                            try:
                                conn.execute(f"ALTER TABLE case_metadata ADD COLUMN {column_name} {column_def}")
                                print(f"✅ Added column: {column_name}")
                            except sqlite3.OperationalError as e:
                                if "duplicate column name" not in str(e).lower():
                                    print(f"⚠️ Could not add column {column_name}: {e}")
                    
                # Create additional tables
                conn.execute("""
                CREATE TABLE IF NOT EXISTS search_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    results_count INTEGER,
                    response_time REAL,
                    user_session TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    session_id TEXT UNIQUE NOT NULL,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                # Create indexes for better performance
                indexes = [
                    ("idx_case_number", "case_metadata", "case_number"),
                    ("idx_file_name", "case_metadata", "file_name"),
                    ("idx_date", "case_metadata", "date"),
                    ("idx_search_timestamp", "search_logs", "timestamp")
                ]
                
                for index_name, table_name, column_name in indexes:
                    try:
                        conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})")
                    except sqlite3.OperationalError:
                        pass  # Index might already exist
                
                conn.commit()
                print("✅ Database tables created/updated successfully")
                
        except Exception as e:
            print(f"❌ Error creating enhanced tables: {e}")
    
    @staticmethod
    def insert_metadata(metadata: Dict) -> bool:
        """Enhanced insert with duplicate handling - compatible with existing insert_metadata"""
        try:
            with get_db_connection() as conn:
                def normalize(value):
                    if isinstance(value, (list, dict)):
                        return json.dumps(value, ensure_ascii=False)
                    return value
                
                # Check if case already exists by file_name
                cursor = conn.execute(
                    "SELECT id FROM case_metadata WHERE file_name = ?",
                    (metadata.get("file_name"),)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    conn.execute("""
                    UPDATE case_metadata SET
                        case_number = ?, petitioner = ?, respondent = ?, 
                        date = ?, judges = ?, acts_referred = ?, summary = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE file_name = ?
                    """, (
                        normalize(metadata.get("case_number")),
                        normalize(metadata.get("petitioner")),
                        normalize(metadata.get("respondent")),
                        normalize(metadata.get("date")),
                        normalize(metadata.get("judges")),
                        normalize(metadata.get("acts_referred")),
                        normalize(metadata.get("summary")),
                        metadata.get("file_name")
                    ))
                    print(f"✅ Updated existing record for {metadata.get('file_name')}")
                else:
                    # Insert new record
                    conn.execute("""
                    INSERT INTO case_metadata 
                    (file_name, case_number, petitioner, respondent, date, judges, acts_referred, summary, file_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metadata.get("file_name"),
                        normalize(metadata.get("case_number")),
                        normalize(metadata.get("petitioner")),
                        normalize(metadata.get("respondent")),
                        normalize(metadata.get("date")),
                        normalize(metadata.get("judges")),
                        normalize(metadata.get("acts_referred")),
                        normalize(metadata.get("summary")),
                        metadata.get("file_path")
                    ))
                    print(f"✅ Inserted new record for {metadata.get('file_name')}")
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ Database insert error: {e}")
            return False
    
    @staticmethod
    def get_case_by_filename(file_name: str) -> Optional[Dict]:
        """Get case by filename"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM case_metadata WHERE file_name = ?",
                    (file_name,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error retrieving case by filename: {e}")
            return None
    
    @staticmethod
    def get_case_by_id(case_id: int) -> Optional[Dict]:
        """Get case by ID"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM case_metadata WHERE id = ?",
                    (case_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error retrieving case by ID: {e}")
            return None
    
    @staticmethod
    def search_cases(query: str, limit: int = 10) -> List[Dict]:
        """Enhanced search across multiple fields"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("""
                SELECT * FROM case_metadata 
                WHERE 
                    case_number LIKE ? OR 
                    petitioner LIKE ? OR 
                    respondent LIKE ? OR 
                    summary LIKE ? OR
                    judges LIKE ?
                ORDER BY id DESC 
                LIMIT ?
                """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error searching cases: {e}")
            return []
    
    @staticmethod
    def get_all_cases(limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all cases with pagination"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM case_metadata ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error retrieving all cases: {e}")
            return []
    
    @staticmethod
    def get_cases_count() -> int:
        """Get total number of cases"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as count FROM case_metadata")
                result = cursor.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            print(f"Error getting cases count: {e}")
            return 0
    
    @staticmethod
    def log_search(query: str, results_count: int, response_time: float, session_id: str = None):
        """Log search for analytics"""
        try:
            with get_db_connection() as conn:
                conn.execute("""
                INSERT INTO search_logs (query, results_count, response_time, user_session)
                VALUES (?, ?, ?, ?)
                """, (query, results_count, response_time, session_id))
                conn.commit()
        except Exception as e:
            print(f"Error logging search: {e}")
    
    @staticmethod
    def get_search_analytics(days: int = 30) -> Dict:
        """Get search analytics"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_searches,
                    AVG(response_time) as avg_response_time,
                    COUNT(DISTINCT query) as unique_queries,
                    AVG(results_count) as avg_results
                FROM search_logs 
                WHERE timestamp > datetime('now', '-{} days')
                """.format(days))
                
                result = cursor.fetchone()
                return dict(result) if result else {
                    "total_searches": 0,
                    "avg_response_time": 0,
                    "unique_queries": 0,
                    "avg_results": 0
                }
        except Exception as e:
            print(f"Error getting search analytics: {e}")
            return {}
    
    @staticmethod
    def get_popular_queries(limit: int = 10) -> List[Dict]:
        """Get most popular search queries"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("""
                SELECT query, COUNT(*) as frequency
                FROM search_logs 
                WHERE timestamp > datetime('now', '-30 days')
                GROUP BY query
                ORDER BY frequency DESC
                LIMIT ?
                """, (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting popular queries: {e}")
            return []