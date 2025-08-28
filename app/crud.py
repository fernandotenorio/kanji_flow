# app/crud.py

import sqlite3
import json
from typing import List, Optional
from datetime import datetime
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
        "INSERT INTO decks (name, card_template, card_css) VALUES (?, ?, ?)", # Add card_css
        (deck.name, deck.card_template, deck.card_css) # Add deck.card_css
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

def get_cards_for_review(
    db: sqlite3.Connection,
    deck_id: int,
    current_date: datetime,
    new_card_limit: int,
    total_limit: int
) -> List[Card]:
    """
    Fetches cards for a review session, prioritizing due cards, then adding new cards.
    The total number of cards is capped by total_limit.
    """
    cursor = db.cursor()

    # 1. Get all cards that are due for review (have been seen before)
    # These are the highest priority. We order by date to show the most "overdue" first.
    cursor.execute(
        """SELECT * FROM cards 
           WHERE deck_id = ? AND reviews > 0 AND next_review_date <= ?
           ORDER BY next_review_date ASC""",
        (deck_id, current_date.isoformat())
    )
    due_review_cards = [_row_to_card(row) for row in cursor.fetchall()]

    # 2. Get a limited number of new cards (have never been seen)
    new_cards_to_add = []
    if new_card_limit > 0:
        cursor.execute(
            """SELECT * FROM cards 
               WHERE deck_id = ? AND reviews = 0
               ORDER BY id ASC 
               LIMIT ?""",
            (deck_id, new_card_limit)
        )
        new_cards_to_add = [_row_to_card(row) for row in cursor.fetchall()]

    # 3. Combine the lists: due reviews first, then new cards
    combined_session = due_review_cards + new_cards_to_add
    
    # 4. Enforce the total session limit (max_reviews_per_day)
    if total_limit > 0:
        return combined_session[:total_limit]
    return combined_session

def create_card(db: sqlite3.Connection, card: CardCreate) -> Card:
    cursor = db.cursor()
    data_json = json.dumps(card.data)
    cursor.execute(
        "INSERT INTO cards (deck_id, data, next_review_date, last_reviewed_date) VALUES (?, ?, ?, ?)",
        (card.deck_id, data_json, datetime.now().isoformat(), None) # Use datetime
    )
    db.commit()
    card_id = cursor.lastrowid
    return get_card(db, card_id)

def update_card_review_data(db: sqlite3.Connection, card_id: int, next_review_date: datetime, interval_days: float, ease_factor: float, reviews: int, last_reviewed_date: datetime) -> Optional[Card]:
    cursor = db.cursor()
    cursor.execute(
        """UPDATE cards SET
            next_review_date = ?,
            interval_days = ?,
            ease_factor = ?,
            reviews = ?,
            last_reviewed_date = ?
           WHERE id = ?""",
        (next_review_date.isoformat(), interval_days, ease_factor, reviews, last_reviewed_date.isoformat(), card_id)
    )
    db.commit()
    return get_card(db, card_id)

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