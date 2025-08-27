import sqlite3
from typing import Optional

DATABASE_URL = "kanji_flow.db"

def get_db():    
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    try:
        yield conn
    finally:
        conn.close()

def create_tables():
    # It's good practice to add the parameter here as well for consistency
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kanji (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character TEXT NOT NULL UNIQUE,
            meaning TEXT NOT NULL,
            onyomi TEXT,
            kunyomi TEXT,
            grade INTEGER,
            stroke_count INTEGER,
            next_review_date TEXT,
            interval_days REAL DEFAULT 0.0,
            ease_factor REAL DEFAULT 2.5,
            reviews INTEGER DEFAULT 0,
            last_reviewed_date TEXT
        );
    """)
    # Table for algorithm settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT NOT NULL UNIQUE,
            setting_value TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

# Call this once when the app starts
# create_tables()