# app/srs_algorithm.py
from datetime import datetime, timedelta, date
from typing import List
from app.models import Card

def sm2_algorithm(
    card: Card,
    quality: int,
    learning_steps_minutes: List[int],
    graduating_interval_days: int
) -> Card:
    """
    Implements a modified SM-2 algorithm that manages card state.
    quality: 0-2 (Hard/Incorrect), 3 (Good), 4-5 (Easy)
    """
    card.last_reviewed_date = datetime.now()

    # If this is the card's first-ever review, stamp its introduction date.
    if card.state == 'new':
        card.introduction_date = date.today()

    if quality < 3:  # --- Incorrect Answer (Lapse) ---
        card.reviews += 1 # A lapse is still a review
        card.learning_step = 0
        card.state = 'learning'
        card.interval_days = 0
        # Optional: Penalize ease factor on lapses for graduated cards
        if card.ease_factor > 1.3:
             card.ease_factor -= 0.2
        
        # Reset to the first learning step
        interval_minutes = learning_steps_minutes[0] if learning_steps_minutes else 10
        card.next_review_date = datetime.now() + timedelta(minutes=interval_minutes)

    else:  # --- Correct Answer ---
        card.reviews += 1
        
        if card.state == 'learning' or card.state == 'new':
            card.state = 'learning'
            # If there are more learning steps, use the next one
            if card.learning_step < len(learning_steps_minutes):
                interval_minutes = learning_steps_minutes[card.learning_step]
                card.next_review_date = datetime.now() + timedelta(minutes=interval_minutes)
                card.learning_step += 1
            # Otherwise, the card graduates
            else:
                card.state = 'review'
                # card.interval_days = graduating_interval_days
                # card.next_review_date = datetime.now() + timedelta(days=graduating_interval_days)
                card.interval_days = graduating_interval_days
                card.next_review_date = datetime.now() + timedelta(minutes=graduating_interval_days)
        
        elif card.state == 'review':
            # This is the first review after graduation
            if card.interval_days == 0:
                 card.interval_days = graduating_interval_days
            else: # Standard SM-2 interval calculation
                card.interval_days = round(card.interval_days * card.ease_factor)
            
            # Update ease factor (only for graduated cards)
            card.ease_factor += (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            if card.ease_factor < 1.3:
                card.ease_factor = 1.3
            
            #card.next_review_date = datetime.now() + timedelta(days=int(card.interval_days))
            card.next_review_date = datetime.now() + timedelta(minutes=card.interval_days)

    return card