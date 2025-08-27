from pydantic import BaseModel
from typing import Optional
from datetime import date

class KanjiBase(BaseModel):
    character: str
    meaning: str
    onyomi: Optional[str] = None
    kunyomi: Optional[str] = None
    grade: Optional[int] = None
    stroke_count: Optional[int] = None

class KanjiCreate(KanjiBase):
    pass

class Kanji(KanjiBase):
    id: int
    next_review_date: date = date.today()
    interval_days: float = 0.0
    ease_factor: float = 2.5
    reviews: int = 0
    last_reviewed_date: Optional[date] = None

    class Config:
        # This is the line to change
        from_attributes = True # Changed from orm_mode = True

class Settings(BaseModel):
    setting_name: str
    setting_value: str