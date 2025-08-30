from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import json
from datetime import date, datetime
from typing import Optional, Dict, Any, List

from app import crud, models
from app.database import get_db, create_tables
from app.srs_algorithm import sm2_algorithm


# Call create_tables once at startup
create_tables()

app = FastAPI()

# --- NO MORE SESSION MIDDLEWARE ---

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Custom Jinja2 global function (Unchanged) ---
def render_template_string(template_string: str, **context) -> str:
    template = templates.env.from_string(template_string)
    return template.render(**context)
templates.env.globals['render_template_string'] = render_template_string
# ---

# Dependency
def get_database():
    yield from get_db()

@app.get("/", response_class=RedirectResponse)
async def read_root():
    return RedirectResponse(url="/decks")

@app.get("/decks", response_class=HTMLResponse)
async def list_decks(request: Request, db: sqlite3.Connection = Depends(get_database)):
    """Displays a list of all created decks with their queue counts."""
    decks_raw = crud.get_all_decks(db)
    decks_with_counts = []
    
    # Get global settings as fallbacks
    global_new_cards = int(crud.get_setting(db, "new_cards_per_day") or "5")
    global_max_reviews = int(crud.get_setting(db, "max_reviews_per_day") or "20")

    # --- NEW: Fetch global learning steps and graduating interval ---
    global_learning_steps = crud.get_setting(db, "learning_steps") or "10 1440" # Default as per sm2_algorithm
    global_graduating_interval = int(crud.get_setting(db, "graduating_interval") or "4") # Default as per sm2_algorithm
    # --- END NEW ---
    
    for deck in decks_raw:
        effective_new_cards = deck.new_cards_per_day or global_new_cards
        effective_max_reviews = deck.max_reviews_per_day or global_max_reviews
        reviews_done_today = crud.get_reviews_done_today(db, deck.id)
        new_cards_rated_today = crud.get_new_cards_rated_today(db, deck.id)

        counts = crud.get_queue_counts(db, deck.id, effective_new_cards)
        decks_with_counts.append({
            "deck": deck,
            "counts": counts,
            "max_reviews_setting": effective_max_reviews,
            "new_cards_per_day_setting": effective_new_cards,
            "reviews_done_today": reviews_done_today,
            "new_cards_rated_today": new_cards_rated_today
        })

    return templates.TemplateResponse("decks.html", {"request": request, "decks_with_counts": decks_with_counts})

@app.get("/add_deck", response_class=HTMLResponse)
async def add_deck_page(request: Request):
    return templates.TemplateResponse("add_deck.html", {"request": request, "message": None, "error": None})

# add_deck_submit POST endpoint remains largely the same, no changes needed here.
@app.post("/add_deck", response_class=HTMLResponse)
async def add_deck_submit(
    request: Request,
    name: str = Form(...),
    card_template: str = Form(...),
    card_css: str = Form(...),
    deck_file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_database)
):
    try:
        new_deck_model = models.DeckCreate(name=name, card_template=card_template, card_css=card_css)
        created_deck = crud.create_deck(db, new_deck_model)
        contents = await deck_file.read()
        cards_data = json.loads(contents)
        if not isinstance(cards_data, list):
            raise ValueError("JSON file must contain a list of card objects.")
        for card_item in cards_data:
            new_card_model = models.CardCreate(deck_id=created_deck.id, data=card_item)
            crud.create_card(db, new_card_model)
        return RedirectResponse(url="/decks", status_code=303)
    except sqlite3.IntegrityError:
        error = f"A deck with the name '{name}' already exists."
        return templates.TemplateResponse("add_deck.html", {"request": request, "error": error, "name": name, "card_template": card_template, "card_css": card_css})
    except (json.JSONDecodeError, ValueError) as e:
        error = f"Invalid JSON file: {e}"
        return templates.TemplateResponse("add_deck.html", {"request": request, "error": error, "name": name, "card_template": card_template, "card_css": card_css})
    except Exception as e:
        error = f"An unexpected error occurred: {e}"
        return templates.TemplateResponse("add_deck.html", {"request": request, "error": error, "name": name, "card_template": card_template, "card_css": card_css})

@app.get("/study/{deck_id}", response_class=HTMLResponse)
async def study_deck(request: Request, deck_id: int, db: sqlite3.Connection = Depends(get_database)):
    deck = crud.get_deck(db, deck_id)
    if not deck:
        return RedirectResponse(url="/decks")

    # Determine effective settings
    global_new_cards = int(crud.get_setting(db, "new_cards_per_day") or "5")
    global_max_reviews = int(crud.get_setting(db, "max_reviews_per_day") or "20")

    # --- NEW: Fetch global learning steps and graduating interval ---
    global_learning_steps = crud.get_setting(db, "learning_steps") or "10 1440"
    global_graduating_interval = int(crud.get_setting(db, "graduating_interval") or "4")
    # --- END NEW ---

    effective_new_cards = deck.new_cards_per_day or global_new_cards
    effective_max_reviews = deck.max_reviews_per_day or global_max_reviews

    # --- NEW DATABASE-DRIVEN GATEKEEPER ---
    reviews_done_today = crud.get_reviews_done_today(db, deck_id)

    if reviews_done_today >= effective_max_reviews:
        return templates.TemplateResponse(
            "study.html", {
                "request": request, "deck": deck, "current_card": None,
                "message": "Session complete. You've reached your daily review limit."
            })
    # --- END OF NEW GATEKEEPER ---

    # Get the next card dynamically
    current_card = crud.get_next_card_for_review(db, deck_id, effective_new_cards, effective_max_reviews)
    
    # Get current queue counts for display
    queue_counts = crud.get_queue_counts(db, deck_id, effective_new_cards)
    
    if not current_card:
        return templates.TemplateResponse(
            "study.html", {
                "request": request, "deck": deck, "current_card": None,
                "message": "Session complete. Well done!", "queue_counts": queue_counts
            })

    return templates.TemplateResponse(
        "study.html", {
            "request": request, "deck": deck, "current_card": current_card,
            "queue_counts": queue_counts
        })

@app.post("/submit_review/{deck_id}", response_class=RedirectResponse)
async def submit_review(
    deck_id: int,
    card_id: int = Form(...),
    quality: int = Form(...),
    db: sqlite3.Connection = Depends(get_database)
):    
    card = crud.get_card(db, card_id)

    if card:
        # --- LOG THE REVIEW ACTION IN THE DATABASE ---
        crud.log_review(db, deck_id=deck_id, card_id=card_id, quality=quality)

        deck = crud.get_deck(db, deck_id)
        # Get effective settings for the algorithm
        global_steps_str = crud.get_setting(db, "learning_steps") or "10 1440"
        global_grad_interval = int(crud.get_setting(db, "graduating_interval") or "4")
        effective_steps_str = deck.learning_steps or global_steps_str
        effective_grad_interval = deck.graduating_interval or global_grad_interval
        learning_steps = [int(step) for step in effective_steps_str.split()]

        # Run the algorithm to get the card's new state
        updated_card_model = sm2_algorithm(card, quality, learning_steps, effective_grad_interval)
        
        # Persist the changes to the database
        crud.update_card_review_data(db, updated_card_model)

    # Redirect back to the study page, which will dynamically pull the next card
    return RedirectResponse(url=f"/study/{deck_id}", status_code=303)        


@app.get("/progress/{deck_id}", response_class=HTMLResponse)
async def deck_progress(request: Request, deck_id: int, db: sqlite3.Connection = Depends(get_database)):
    deck = crud.get_deck(db, deck_id)
    if not deck:
        return RedirectResponse(url="/decks")
    all_cards = crud.get_all_cards_in_deck(db, deck_id)
    all_cards_sorted = sorted(all_cards, key=lambda c: c.next_review_date)
    return templates.TemplateResponse("progress_deck.html", {"request": request, "deck": deck, "all_cards": all_cards_sorted})

@app.get("/settings/{deck_id}", response_class=HTMLResponse)
async def deck_settings_page(request: Request, deck_id: int, db: sqlite3.Connection = Depends(get_database)):
    deck = crud.get_deck(db, deck_id)
    if not deck:
        return RedirectResponse(url="/decks")
    global_new = crud.get_setting(db, "new_cards_per_day") or "5"
    global_max = crud.get_setting(db, "max_reviews_per_day") or "20"

    # --- NEW: Fetch global learning steps and graduating interval ---
    global_learning_steps = crud.get_setting(db, "learning_steps") or "10 1440"
    global_graduating_interval = int(crud.get_setting(db, "graduating_interval") or "4")
    # --- END NEW ---

    return templates.TemplateResponse(
        "settings_deck.html",
        {
            "request": request,
            "deck": deck,
            "global_new_cards_per_day": global_new,
            "global_max_reviews_per_day": global_max,
            # --- NEW: Pass global learning steps and graduating interval ---
            "global_learning_steps": global_learning_steps,
            "global_graduating_interval": global_graduating_interval,
            # --- END NEW ---
            "message": None
        }
    )

@app.post("/settings/{deck_id}", response_class=HTMLResponse)
async def update_deck_settings_submit(
    request: Request,
    deck_id: int,
    new_cards_per_day: Optional[str] = Form(None),
    max_reviews_per_day: Optional[str] = Form(None),
    learning_steps: Optional[str] = Form(None),
    graduating_interval: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_database)
):
    new_cards_val = int(new_cards_per_day) if new_cards_per_day else None
    max_reviews_val = int(max_reviews_per_day) if max_reviews_per_day else None
    graduating_interval_val = int(graduating_interval) if graduating_interval else None
    crud.update_deck_settings(db, deck_id, new_cards_val, max_reviews_val, learning_steps, graduating_interval_val)
    deck = crud.get_deck(db, deck_id)
    global_new = crud.get_setting(db, "new_cards_per_day") or "5"
    global_max = crud.get_setting(db, "max_reviews_per_day") or "20"

    # --- NEW: Fetch global learning steps and graduating interval for re-render ---
    global_learning_steps = crud.get_setting(db, "learning_steps") or "10 1440"
    global_graduating_interval = int(crud.get_setting(db, "graduating_interval") or "4")
    # --- END NEW ---

    return templates.TemplateResponse(
        "settings_deck.html",
        {
            "request": request,
            "deck": deck,
            "global_new_cards_per_day": global_new,
            "global_max_reviews_per_day": global_max,
            # --- NEW: Pass global learning steps and graduating interval ---
            "global_learning_steps": global_learning_steps,
            "global_graduating_interval": global_graduating_interval,
            # --- END NEW ---
            "message": "Deck settings updated successfully!"
        }
    )

@app.post("/delete_deck/{deck_id}", response_class=RedirectResponse)
async def delete_deck_submit(deck_id: int, db: sqlite3.Connection = Depends(get_database)):
    crud.delete_deck(db, deck_id)
    return RedirectResponse(url="/decks", status_code=303)

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: sqlite3.Connection = Depends(get_database)):
    current_new_cards_per_day = crud.get_setting(db, "new_cards_per_day") or "5"
    current_max_reviews_per_day = crud.get_setting(db, "max_reviews_per_day") or "20"

    # --- NEW: Fetch global learning steps and graduating interval ---
    current_learning_steps = crud.get_setting(db, "learning_steps") or "10 1440"
    current_graduating_interval = crud.get_setting(db, "graduating_interval") or "4"
    # --- END NEW ---

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "new_cards_per_day": current_new_cards_per_day,
            "max_reviews_per_day": current_max_reviews_per_day,
            # --- NEW: Pass global learning steps and graduating interval ---
            "learning_steps": current_learning_steps,
            "graduating_interval": current_graduating_interval,
            # --- END NEW ---
            "message": None
        }
    )

@app.post("/settings", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    new_cards_per_day: int = Form(...),
    max_reviews_per_day: int = Form(...),
    learning_steps: str = Form(...),
    graduating_interval: int = Form(...),
    db: sqlite3.Connection = Depends(get_database)
):
    crud.set_setting(db, "new_cards_per_day", str(new_cards_per_day))
    crud.set_setting(db, "max_reviews_per_day", str(max_reviews_per_day))

    # --- NEW: Update global learning steps and graduating interval ---
    crud.set_setting(db, "learning_steps", learning_steps)
    crud.set_setting(db, "graduating_interval", str(graduating_interval))
    # --- END NEW ---

    message = "Settings updated successfully!"
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "new_cards_per_day": new_cards_per_day,
            "max_reviews_per_day": max_reviews_per_day,
            # --- NEW: Pass updated learning steps and graduating interval ---
            "learning_steps": learning_steps,
            "graduating_interval": graduating_interval,
            # --- END NEW ---
            "message": message
        }
    )