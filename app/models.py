# app/models.py

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import date

# --- Deck Models ---

class DeckBase(BaseModel):
    name: str
    card_template: str  # To store the Jinja2 template for rendering cards
    card_css: str

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
    next_review_date: date = date.today()
    interval_days: float = 0.0
    ease_factor: float = 2.5
    reviews: int = 0
    last_reviewed_date: Optional[date] = None

    class Config:
        from_attributes = True

# --- Settings Model (Unchanged) ---
class Settings(BaseModel):
    setting_name: str
    setting_value: str