import sqlite3

def create_db():
    conn = sqlite3.connect("cases_metadata.db")
    cursor = conn.cursor()

    cursor.execute("""
     CREATE TABLE IF NOT EXISTS case_metadata (
        id INTEGER PRIMARY KEY,
        file_name TEXT NOT NULL,
        title TEXT,
        date TEXT,
        judges TEXT,
        summary TEXT,
        file_path TEXT,
        content_hash TEXT,
        vector_stored BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_db()
    print("✅ Database and table created!")
