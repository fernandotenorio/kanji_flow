# app/database.py

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
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    cursor = conn.cursor()

    # Create decks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            card_template TEXT NOT NULL,
            card_css TEXT NOT NULL,
            new_cards_per_day INTEGER,
            max_reviews_per_day INTEGER
        );
    """)

    # Create cards table (generalized from kanji)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            data TEXT NOT NULL, -- Storing card data as a JSON string
            next_review_date TEXT,
            interval_days REAL DEFAULT 0.0,
            ease_factor REAL DEFAULT 2.5,
            reviews INTEGER DEFAULT 0,
            last_reviewed_date TEXT,
            FOREIGN KEY(deck_id) REFERENCES decks(id)
        );
    """)
    
    # Table for app settings (unchanged)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT NOT NULL UNIQUE,
            setting_value TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()