import sqlite3

def check_db():
    conn = sqlite3.connect('jobai.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT suggestion_type FROM tailoring_sessions")
    rows = cursor.fetchall()
    print("Unique suggestion types:", rows)
    conn.close()

if __name__ == "__main__":
    check_db()
