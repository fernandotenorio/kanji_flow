# app/models.py

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import date, datetime

# --- Deck Models ---
class DeckBase(BaseModel):
    name: str
    card_template: str
    card_css: str
    new_cards_per_day: Optional[int] = None
    max_reviews_per_day: Optional[int] = None
    learning_steps: Optional[str] = None      # e.g., "10 1440"
    graduating_interval: Optional[int] = None # e.g., 4 (days)

class DeckCreate(DeckBase):
    pass

class Deck(DeckBase):
    id: int

    class Config:
        from_attributes = True

# --- Card Models ---

class CardBase(BaseModel):
    # This dictionary will hold the card's content, e.g., {"front": "...", "back": "..."}
    data: Dict[str, Any]

class CardCreate(CardBase):
    deck_id: int

class Card(CardCreate):
    id: int
    next_review_date: datetime = datetime.now()
    interval_days: float = 0.0
    ease_factor: float = 2.5
    reviews: int = 0
    last_reviewed_date: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Settings Model (Unchanged) ---
class Settings(BaseModel):
    setting_name: str
    setting_value: str