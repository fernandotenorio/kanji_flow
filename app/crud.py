import sqlite3
from typing import List, Optional
from datetime import date, timedelta
from app.models import KanjiCreate, Kanji, Settings

# --- Kanji CRUD ---
def get_kanji(db: sqlite3.Connection, kanji_id: int) -> Optional[Kanji]:
    cursor = db.cursor()
    cursor.execute("SELECT * FROM kanji WHERE id = ?", (kanji_id,))
    row = cursor.fetchone()
    # Convert row to dict before validation
    return Kanji.model_validate(dict(row)) if row else None

def get_all_kanji(db: sqlite3.Connection) -> List[Kanji]:
    cursor = db.cursor()
    cursor.execute("SELECT * FROM kanji")
    # Convert each row to a dict in the list comprehension
    return [Kanji.model_validate(dict(row)) for row in cursor.fetchall()]

def get_kanji_for_review(db: sqlite3.Connection, current_date: date) -> List[Kanji]:
    cursor = db.cursor()
    # Select kanji where next_review_date is today or earlier
    cursor.execute("SELECT * FROM kanji WHERE next_review_date <= ?", (current_date.isoformat(),))
    # Convert each row to a dict in the list comprehension
    return [Kanji.model_validate(dict(row)) for row in cursor.fetchall()]

def create_kanji(db: sqlite3.Connection, kanji: KanjiCreate) -> Kanji:
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO kanji (character, meaning, onyomi, kunyomi, grade, stroke_count, next_review_date, last_reviewed_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (kanji.character, kanji.meaning, kanji.onyomi, kanji.kunyomi, kanji.grade, kanji.stroke_count, date.today().isoformat(), None)
    )
    db.commit()
    kanji_id = cursor.lastrowid
    return get_kanji(db, kanji_id)

def update_kanji_review_data(db: sqlite3.Connection, kanji_id: int, next_review_date: date, interval_days: float, ease_factor: float, reviews: int, last_reviewed_date: date) -> Optional[Kanji]:
    cursor = db.cursor()
    cursor.execute(
        """UPDATE kanji SET
            next_review_date = ?,
            interval_days = ?,
            ease_factor = ?,
            reviews = ?,
            last_reviewed_date = ?
           WHERE id = ?""",
        (next_review_date.isoformat(), interval_days, ease_factor, reviews, last_reviewed_date.isoformat(), kanji_id)
    )
    db.commit()
    return get_kanji(db, kanji_id)

def delete_kanji(db: sqlite3.Connection, kanji_id: int):
    cursor = db.cursor()
    cursor.execute("DELETE FROM kanji WHERE id = ?", (kanji_id,))
    db.commit()

# --- Settings CRUD ---
def get_setting(db: sqlite3.Connection, setting_name: str) -> Optional[str]:
    cursor = db.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_name = ?", (setting_name,))
    row = cursor.fetchone()
    return row[0] if row else None

def set_setting(db: sqlite3.Connection, setting_name: str, setting_value: str) -> Settings:
    cursor = db.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (setting_name, setting_value) VALUES (?, ?)",
        (setting_name, setting_value)
    )
    db.commit()
    return Settings(setting_name=setting_name, setting_value=setting_value)

def get_all_settings(db: sqlite3.Connection) -> List[Settings]:
    cursor = db.cursor()
    cursor.execute("SELECT * FROM settings")
    return [Settings.parse_obj(row) for row in cursor.fetchall()]