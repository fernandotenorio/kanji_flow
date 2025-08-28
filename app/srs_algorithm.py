# app/srs_algorithm.py
from datetime import datetime, timedelta
from typing import List
from app.models import Card

def sm2_algorithm(
    card: Card,
    quality: int,
    learning_steps_minutes: List[int],
    graduating_interval_days: int
) -> Card:
    """
    Implements a modified SM-2 algorithm with configurable learning steps.
    quality: 0-2 (Hard/Incorrect), 3 (Good), 4-5 (Easy)
    """
    ease_factor = card.ease_factor
    interval_days = card.interval_days
    reviews = card.reviews

    if quality >= 3:  # Correct answer
        # Check if the card is still in the learning phase
        if reviews < len(learning_steps_minutes):
            interval_minutes = learning_steps_minutes[reviews]
            card.next_review_date = datetime.now() + timedelta(minutes=interval_minutes)
            card.interval_days = 0  # Keep interval at 0 until graduation
        else:  # Card is graduating or is already graduated
            # If this is the first review after learning steps, use the graduating interval
            if interval_days == 0:
                interval_days = graduating_interval_days
            else: # Standard SM-2 for already graduated cards
                interval_days = round(interval_days * ease_factor)

            # Ease factor adjustment only happens on graduated cards
            ease_factor += (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            if ease_factor < 1.3:
                ease_factor = 1.3
            
            card.next_review_date = datetime.now() + timedelta(days=interval_days)
        
        reviews += 1
    else:  # Incorrect answer
        # Reset the card to the beginning of the learning phase
        reviews = 0
        interval_days = 0 # Reset interval
        # Use the first learning step
        interval_minutes = learning_steps_minutes[0] if learning_steps_minutes else 10
        card.next_review_date = datetime.now() + timedelta(minutes=interval_minutes)
        # Optional: Penalize ease factor on lapses for graduated cards
        if card.interval_days > 0 and ease_factor > 1.3:
             ease_factor -= 0.2
    
    card.ease_factor = ease_factor
    card.interval_days = interval_days
    card.reviews = reviews
    card.last_reviewed_date = datetime.now()

    return card