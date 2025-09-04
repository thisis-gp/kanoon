import sqlite3
import json

def insert_metadata(metadata):
    conn = sqlite3.connect("cases_metadata.db")
    cursor = conn.cursor()

    def normalize(value):
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return value

    cursor.execute("""
    INSERT INTO case_metadata (file_name, case_number, petitioner, respondent, date, judges, acts_referred, summary, file_path)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        normalize(metadata.get("file_name")),
        normalize(metadata.get("case_number")),
        normalize(metadata.get("petitioner")),
        normalize(metadata.get("respondent")),
        normalize(metadata.get("date")),
        normalize(metadata.get("judges")),
        normalize(metadata.get("acts_referred")),
        normalize(metadata.get("summary")),
        normalize(metadata.get("file_path")),
    ))

    conn.commit()
    conn.close()