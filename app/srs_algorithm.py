# app/srs_algorithm.py

from datetime import date, timedelta
from app.models import Card # Change this from Kanji

def sm2_algorithm(card: Card, quality: int) -> Card: # Change the type hint here
    """
    Implements the SuperMemo 2 (SM-2) algorithm.
    quality: 0-2 (Hard), 3 (Good), 4-5 (Easy) mapping for button clicks.
    """
    # ... the rest of the function remains the same
    ease_factor = card.ease_factor
    interval_days = card.interval_days
    reviews = card.reviews

    if quality >= 3: # Correct answer (Good or Easy)
        if reviews == 0:
            interval_days = 1
        elif reviews == 1:
            interval_days = 6
        else:
            interval_days = round(interval_days * ease_factor)

        reviews += 1
        ease_factor += (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if ease_factor < 1.3:
            ease_factor = 1.3
    else: # Incorrect answer (Hard, or forgotten)
        reviews = 0 # Reset reviews for this card
        interval_days = 1 # Review tomorrow
        # No change to ease_factor if quality is 0, 1, 2. If it was 0, ease_factor could decrease.
        # For simplicity, let's just use 0-2 as "Hard" and reset interval.
        # A more faithful implementation might slightly decrease ease_factor for quality 0-2.

    next_review_date = date.today() + timedelta(days=interval_days)

    card.next_review_date = next_review_date
    card.interval_days = interval_days
    card.ease_factor = ease_factor
    card.reviews = reviews
    card.last_reviewed_date = date.today()

    return card