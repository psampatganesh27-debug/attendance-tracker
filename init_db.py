import sqlite3

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Drop old tables if they exist so new constraints take effect
    cursor.execute("DROP TABLE IF EXISTS attendance_logs")
    cursor.execute("DROP TABLE IF EXISTS schedule")
    cursor.execute("DROP TABLE IF EXISTS holidays")
    cursor.execute("DROP TABLE IF EXISTS subjects")

    # Recreate tables cleanly
    cursor.execute("""
    CREATE TABLE subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        target_percentage REAL DEFAULT 80.0
    );
    """)

    cursor.execute("""
    CREATE TABLE schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        day_of_week INTEGER NOT NULL,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE holidays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        holiday_date TEXT UNIQUE NOT NULL,
        description TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE attendance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        class_date TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'PRESENT', 'ABSENT', 'CANCELLED')),
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
    print("Database reset and initialized successfully.")

if __name__ == '__main__':
    init_db()