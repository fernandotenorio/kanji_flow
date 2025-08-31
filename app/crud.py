# app/crud.py

import sqlite3
import json
from typing import List, Optional, Dict
from datetime import datetime, date
from app.models import DeckCreate, Deck, CardCreate, Card, Settings

# --- Helper function to parse a row into a Card model ---
def _row_to_card(row: sqlite3.Row) -> Optional[Card]:
    if not row:
        return None
    card_dict = dict(row)
    card_dict['data'] = json.loads(card_dict['data']) # Deserialize JSON string to dict
    return Card.model_validate(card_dict)

# --- Deck CRUD ---
def create_deck(db: sqlite3.Connection, deck: DeckCreate) -> Deck:
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO decks (name, card_template, card_css, media_folder) VALUES (?, ?, ?, ?)",
        (deck.name, deck.card_template, deck.card_css, deck.media_folder)
    )
    db.commit()
    deck_id = cursor.lastrowid
    return get_deck(db, deck_id)

def get_deck(db: sqlite3.Connection, deck_id: int) -> Optional[Deck]:
    cursor = db.cursor()
    cursor.execute("SELECT * FROM decks WHERE id = ?", (deck_id,))
    row = cursor.fetchone()
    return Deck.model_validate(dict(row)) if row else None

def get_all_decks(db: sqlite3.Connection) -> List[Deck]:
    cursor = db.cursor()
    cursor.execute("SELECT * FROM decks")
    return [Deck.model_validate(dict(row)) for row in cursor.fetchall()]

def update_deck_settings(db: sqlite3.Connection, deck_id: int, new_cards: Optional[int], max_reviews: Optional[int], learning_steps: Optional[str], graduating_interval: Optional[int]) -> Optional[Deck]:
    cursor = db.cursor()
    cursor.execute(
        """UPDATE decks SET
            new_cards_per_day = ?, max_reviews_per_day = ?,
            learning_steps = ?, graduating_interval = ?
           WHERE id = ?""",
        (new_cards, max_reviews, learning_steps, graduating_interval, deck_id)
    )
    db.commit()
    return get_deck(db, deck_id)

def delete_deck(db: sqlite3.Connection, deck_id: int):
    cursor = db.cursor()
    cursor.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    db.commit()

# --- Card CRUD ---
def get_card(db: sqlite3.Connection, card_id: int) -> Optional[Card]:
    cursor = db.cursor()
    cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
    row = cursor.fetchone()
    return _row_to_card(row)

def get_all_cards_in_deck(db: sqlite3.Connection, deck_id: int) -> List[Card]:
    cursor = db.cursor()
    cursor.execute("SELECT * FROM cards WHERE deck_id = ?", (deck_id,))
    return [_row_to_card(row) for row in cursor.fetchall()]

def get_queue_counts(db: sqlite3.Connection, deck_id: int, new_card_limit: int) -> Dict[str, int]:
    """Gets the count of cards in each queue for a given deck."""
    cursor = db.cursor()
    now_iso = datetime.now().isoformat()
    today_iso = date.today().isoformat()

    # Learning cards due now
    cursor.execute(
        "SELECT COUNT(*) FROM cards WHERE deck_id = ? AND state = 'learning' AND next_review_date <= ?",
        (deck_id, now_iso)
    )
    learning_count = cursor.fetchone()[0]

    # Review cards due today
    cursor.execute(
        "SELECT * FROM cards WHERE deck_id = ? AND state = 'review' AND next_review_date <= ?",
        (deck_id, today_iso)
    )
    review_count = len(cursor.fetchall())

    # New cards available today
    # 1. Count how many new cards have already been introduced today.
    # cursor.execute(
    #     "SELECT COUNT(*) FROM cards WHERE deck_id = ? AND date(introduction_date) = ?",
    #     (deck_id, today_iso)
    # )
    # new_cards_introduced_today = cursor.fetchone()[0]

    # # 2. Calculate the number of "new card slots" remaining for today.
    # # It can't be negative, so we use max(0, ...).
    # remaining_new_slots = max(0, new_card_limit - new_cards_introduced_today)

    # 3. Count how many cards are actually in the 'new' state.
    cursor.execute(
        "SELECT COUNT(*) FROM cards WHERE deck_id = ? AND state = 'new'",
        (deck_id,)
    )
    actual_new_cards_in_deck = cursor.fetchone()[0]
    
    # 4. The number to display is the smaller of the remaining slots and the actual new cards available.
    new_count = actual_new_cards_in_deck # min(remaining_new_slots, actual_new_cards_in_deck)
    return {"learning": learning_count, "review": review_count, "new": new_count}


def get_next_card_for_review(db: sqlite3.Connection, deck_id: int, new_card_limit: int, total_limit: int) -> Optional[Card]:
    """
    Fetches the single most important card to review right now, based on Anki's queue priorities.
    """
    cursor = db.cursor()
    now_iso = datetime.now().isoformat()
    today_iso = date.today().isoformat()
    
    # --- Priority 1: Learning cards due now ---
    cursor.execute(
        """SELECT * FROM cards 
           WHERE deck_id = ? AND state = 'learning' AND next_review_date <= ?
           ORDER BY next_review_date ASC LIMIT 1""",
        (deck_id, now_iso)
    )
    card = _row_to_card(cursor.fetchone())
    if card:
        return card

    # --- Priority 2: Review cards due today ---
    cursor.execute(
        """SELECT * FROM cards 
           WHERE deck_id = ? AND state = 'review' AND date(next_review_date) <= ?           
           ORDER BY next_review_date ASC LIMIT 1""",
        (deck_id, today_iso)
    )
    card = _row_to_card(cursor.fetchone())
    if card:
        return card

    # --- Priority 3: New cards, up to the daily limit ---
    # Count how many new cards have been introduced today
    cursor.execute(
        "SELECT COUNT(*) FROM cards WHERE deck_id = ? AND date(introduction_date) = ?",
        (deck_id, today_iso)
    )
    new_cards_introduced_today = cursor.fetchone()[0]
    
    if new_cards_introduced_today < new_card_limit:
        cursor.execute(
            """SELECT * FROM cards 
               WHERE deck_id = ? AND state = 'new'
               ORDER BY id ASC LIMIT 1""",
            (deck_id,)
        )
        card = _row_to_card(cursor.fetchone())
        if card:
            return card

    # If we reach here, there's nothing left to study for today
    return None

def create_card(db: sqlite3.Connection, card: CardCreate) -> Card:
    cursor = db.cursor()
    data_json = json.dumps(card.data)
    # We must explicitly set next_review_date to prevent a NULL value
    # that would fail Pydantic validation.
    cursor.execute(
        "INSERT INTO cards (deck_id, data, next_review_date) VALUES (?, ?, ?)",
        (card.deck_id, data_json, datetime.now().isoformat())
    )
    db.commit()
    card_id = cursor.lastrowid
    return get_card(db, card_id)

def update_card_review_data(db: sqlite3.Connection, card: Card) -> Optional[Card]:
    cursor = db.cursor()

    # Convert introduction_date to ISO format if it exists
    intro_date_iso = card.introduction_date.isoformat() if card.introduction_date else None
    last_reviewed_iso = card.last_reviewed_date.isoformat() if card.last_reviewed_date else None

    cursor.execute(
        """UPDATE cards SET
            next_review_date = ?,
            interval_days = ?,
            ease_factor = ?,
            reviews = ?,
            last_reviewed_date = ?,
            state = ?,
            learning_step = ?,
            introduction_date = ?
           WHERE id = ?""",
        (
            card.next_review_date.isoformat(), card.interval_days, card.ease_factor,
            card.reviews, last_reviewed_iso, card.state,
            card.learning_step, intro_date_iso, card.id
        )
    )
    db.commit()
    return get_card(db, card.id)

def delete_card(db: sqlite3.Connection, card_id: int):
    cursor = db.cursor()
    cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    db.commit()

# --- Settings CRUD (Unchanged) ---
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
    return [Settings.model_validate(dict(row)) for row in cursor.fetchall()]

def log_review(db: sqlite3.Connection, deck_id: int, card_id: int, quality: int):
    """Inserts a record of a single review action into the history table."""
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO review_history (deck_id, card_id, review_timestamp, quality) VALUES (?, ?, ?, ?)",
        (deck_id, card_id, datetime.now().isoformat(), quality)
    )
    db.commit()

def get_reviews_done_today(db: sqlite3.Connection, deck_id: int) -> int:
    """Counts the number of review actions logged today for a specific deck."""
    cursor = db.cursor()
    today_iso = date.today().isoformat()
    cursor.execute(
        "SELECT COUNT(*) FROM review_history WHERE deck_id = ? AND date(review_timestamp) = ?",
        (deck_id, today_iso)
    )
    return cursor.fetchone()[0]

def get_new_cards_rated_today(db: sqlite3.Connection, deck_id: int) -> int:
    """Counts how many new cards have had their first review today."""
    cursor = db.cursor()
    today_iso = date.today().isoformat()
    cursor.execute(
        "SELECT COUNT(*) FROM cards WHERE deck_id = ? AND date(introduction_date) = ?",
        (deck_id, today_iso)
    )
    return cursor.fetchone()[0]