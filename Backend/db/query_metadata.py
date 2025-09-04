import sqlite3

def search_cases_by_judge(judge_name):
    conn = sqlite3.connect("cases_metadata.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM case_metadata
    WHERE judges LIKE ?
    """, (f"%{judge_name}%",))

    results = cursor.fetchall()
    conn.close()
    return results

def show_all_cases():
    conn = sqlite3.connect("cases_metadata.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM case_metadata")
    results = cursor.fetchall()
    conn.close()
    return results

if __name__ == "__main__":
    # Only run this when the file is executed directly, not when imported
    try:
        cases = show_all_cases()
        print(f"Found {len(cases)} cases in database")
        for case in cases[:5]:  # Show first 5 cases
            print(f"- {case[1]}")  # file_name
    except Exception as e:
        print(f"Error: {e}")
