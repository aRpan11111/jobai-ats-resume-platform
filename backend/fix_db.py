import sqlite3

def fix_db():
    conn = sqlite3.connect('app/jobai.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE tailoring_sessions SET suggestion_type = 'clarify' WHERE suggestion_type = 'ask'")
    conn.commit()
    print("Updated", cursor.rowcount, "rows")
    conn.close()

if __name__ == "__main__":
    fix_db()
