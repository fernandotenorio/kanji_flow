from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import sqlite3
import json
from datetime import date
from typing import Optional, Dict, Any

from app import crud, models
from app.database import get_db, create_tables


# Call create_tables once at startup
create_tables()

app = FastAPI()

# --- SECRET KEY AND SESSION MIDDLEWARE ---
# IMPORTANT: In a real production app, this key should be a long, random
# string and loaded from an environment variable, not hardcoded.
SECRET_KEY = "a_very_secret_key_for_development"
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
# ----------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- THIS IS THE NEW CODE BLOCK TO ADD ---
# Create a custom global function that can be used in any template.
# This function takes a template string and a context dict, and renders it.
def render_template_string(template_string: str, **context) -> str:
    """Renders a template from a string."""
    template = templates.env.from_string(template_string)
    return template.render(**context)

# Register the function as a global for the Jinja2 environment
templates.env.globals['render_template_string'] = render_template_string
# --- END OF NEW CODE BLOCK ---

# Dependency
def get_database():
    yield from get_db()

@app.get("/", response_class=RedirectResponse)
async def read_root():
    """Redirects the root URL to the main decks page."""
    return RedirectResponse(url="/decks")

@app.get("/decks", response_class=HTMLResponse)
async def list_decks(request: Request, db: sqlite3.Connection = Depends(get_database)):
    """Displays a list of all created decks."""
    decks = crud.get_all_decks(db)
    return templates.TemplateResponse("decks.html", {"request": request, "decks": decks})

@app.get("/add_deck", response_class=HTMLResponse)
async def add_deck_page(request: Request):
    """Shows the form to create a new deck."""
    return templates.TemplateResponse("add_deck.html", {"request": request, "message": None, "error": None})


@app.post("/add_deck", response_class=HTMLResponse)
async def add_deck_submit(
    request: Request,
    name: str = Form(...),
    card_template: str = Form(...),
    card_css: str = Form(...), # Add this line
    deck_file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_database)
):
    """Processes the new deck form submission."""
    try:
        # Step 1: Create the Deck entity in the database
        new_deck_model = models.DeckCreate(
            name=name,
            card_template=card_template,
            card_css=card_css # Add this line
        )
        created_deck = crud.create_deck(db, new_deck_model)

        # ... (rest of the function is the same) ...
        # Step 2: Read and parse the uploaded JSON file
        contents = await deck_file.read()
        cards_data = json.loads(contents)

        if not isinstance(cards_data, list):
            raise ValueError("JSON file must contain a list of card objects.")

        # Step 3: Create a card for each item in the JSON file
        count = 0
        for card_item in cards_data:
            new_card_model = models.CardCreate(
                deck_id=created_deck.id,
                data=card_item
            )
            crud.create_card(db, new_card_model)
            count += 1
        
        return RedirectResponse(url="/decks", status_code=303)

    except sqlite3.IntegrityError:
        error = f"A deck with the name '{name}' already exists."
        # Pass form data back to re-populate the form on error
        return templates.TemplateResponse("add_deck.html", {"request": request, "error": error, "name": name, "card_template": card_template, "card_css": card_css})
    except (json.JSONDecodeError, ValueError) as e:
        error = f"Invalid JSON file: {e}"
        return templates.TemplateResponse("add_deck.html", {"request": request, "error": error, "name": name, "card_template": card_template, "card_css": card_css})
    except Exception as e:
        error = f"An unexpected error occurred: {e}"
        return templates.TemplateResponse("add_deck.html", {"request": request, "error": error, "name": name, "card_template": card_template, "card_css": card_css})


# Study session
    deck = crud.get_deck(db, deck_id)
    if not deck:
        return RedirectResponse(url="/decks")

    # --- COMPLETE SETTINGS LOGIC ---
    # Get global settings as fallbacks
    global_new_cards = int(crud.get_setting(db, "new_cards_per_day") or "5")
    global_max_reviews = int(crud.get_setting(db, "max_reviews_per_day") or "20")
    
    # Determine the effective settings: deck-specific, or global if not set
    effective_new_cards = deck.new_cards_per_day or global_new_cards
    effective_max_reviews = deck.max_reviews_per_day or global_max_reviews
    
    # Use the effective settings in the powerful new CRUD call
    cards_to_review = crud.get_cards_for_review(
        db,
        deck_id,
        date.today(),
        new_card_limit=effective_new_cards,
        total_limit=effective_max_reviews
    )
    
    # (The rest of the function remains the same as before)
    if not cards_to_review:
        return templates.TemplateResponse(
            "study.html",
            {
                "request": request,
                "deck": deck,
                "current_card": None,
                "message": "No cards to review in this deck today. Well done!"
            }
        )
    current_card = cards_to_review[0]
    return templates.TemplateResponse(
        "study.html",
        {
            "request": request,
            "deck": deck,
            "current_card": current_card,
            "total_reviews_today": len(cards_to_review)
        }
    )
@app.get("/study/{deck_id}", response_class=HTMLResponse)
async def study_deck(request: Request, deck_id: int, db: sqlite3.Connection = Depends(get_database)):
    deck = crud.get_deck(db, deck_id)
    if not deck:
        return RedirectResponse(url="/decks")

    session = request.session
    session_key = f"study_session_deck_{deck_id}"

    # If there's no list of card IDs in the session, start a new session
    if session_key not in session:
        global_new_cards = int(crud.get_setting(db, "new_cards_per_day") or "5")
        global_max_reviews = int(crud.get_setting(db, "max_reviews_per_day") or "20")
        effective_new_cards = deck.new_cards_per_day or global_new_cards
        effective_max_reviews = deck.max_reviews_per_day or global_max_reviews

        cards_for_session = crud.get_cards_for_review(
            db, deck_id, date.today(),
            new_card_limit=effective_new_cards,
            total_limit=effective_max_reviews
        )
        # Store only the IDs in the session
        session[session_key] = [card.id for card in cards_for_session]
        session[f"{session_key}_total"] = len(cards_for_session) # Store original total for display

    card_ids_in_session = session[session_key]
    total_cards_in_session = session.get(f"{session_key}_total", 0)

    # If the list of IDs is empty, the session is over
    if not card_ids_in_session:
        # Clear session keys to allow a new session to start next time
        session.pop(session_key, None)
        session.pop(f"{session_key}_total", None)
        return templates.TemplateResponse(
            "study.html", {
                "request": request, "deck": deck, "current_card": None,
                "message": "Session complete. Well done!"
            })

    # Get the next card to study from the list
    next_card_id = card_ids_in_session[0]
    current_card = crud.get_card(db, next_card_id)

    return templates.TemplateResponse(
        "study.html", {
            "request": request, "deck": deck, "current_card": current_card,
            "reviews_left": len(card_ids_in_session),
            "total_reviews_today": total_cards_in_session
        })

@app.post("/submit_review/{deck_id}", response_class=RedirectResponse)
async def submit_review(
    request: Request, # Add request to access the session
    deck_id: int,
    card_id: int = Form(...),
    quality: int = Form(...),
    db: sqlite3.Connection = Depends(get_database)
):
    from app.srs_algorithm import sm2_algorithm
    card = crud.get_card(db, card_id)
    if card:
        updated_card = sm2_algorithm(card, quality)
        crud.update_card_review_data(
            db, updated_card.id, updated_card.next_review_date,
            updated_card.interval_days, updated_card.ease_factor,
            updated_card.reviews, updated_card.last_reviewed_date
        )

    # --- SESSION UPDATE LOGIC ---
    session_key = f"study_session_deck_{deck_id}"
    if session_key in request.session:
        card_ids = request.session[session_key]
        # Remove the card we just reviewed from the front of the list
        if card_ids and card_ids[0] == card_id:
            request.session[session_key] = card_ids[1:]

    return RedirectResponse(url=f"/study/{deck_id}", status_code=303)        

@app.get("/end_session/{deck_id}", response_class=RedirectResponse)
async def end_session(request: Request, deck_id: int):
    session_key = f"study_session_deck_{deck_id}"
    if session_key in request.session:
        request.session.pop(session_key, None)
        request.session.pop(f"{session_key}_total", None)
    return RedirectResponse(url="/decks")

@app.get("/progress/{deck_id}", response_class=HTMLResponse)
async def deck_progress(request: Request, deck_id: int, db: sqlite3.Connection = Depends(get_database)):
    deck = crud.get_deck(db, deck_id)
    if not deck:
        return RedirectResponse(url="/decks")

    # Fetch all cards in the deck
    all_cards = crud.get_all_cards_in_deck(db, deck_id)
    
    # Sort cards for a consistent view, e.g., by next review date
    all_cards_sorted = sorted(all_cards, key=lambda c: c.next_review_date)

    return templates.TemplateResponse(
        "progress_deck.html",
        {
            "request": request,
            "deck": deck,
            "all_cards": all_cards_sorted
        }
    )

@app.get("/settings/{deck_id}", response_class=HTMLResponse)
async def deck_settings_page(request: Request, deck_id: int, db: sqlite3.Connection = Depends(get_database)):
    deck = crud.get_deck(db, deck_id)
    if not deck:
        return RedirectResponse(url="/decks")

    # Get global settings to show as placeholders/defaults
    global_new = crud.get_setting(db, "new_cards_per_day") or "5"
    global_max = crud.get_setting(db, "max_reviews_per_day") or "20"

    return templates.TemplateResponse(
        "settings_deck.html",
        {
            "request": request,
            "deck": deck,
            "global_new_cards_per_day": global_new,
            "global_max_reviews_per_day": global_max,
            "message": None
        }
    )

@app.post("/settings/{deck_id}", response_class=HTMLResponse)
async def update_deck_settings(
    request: Request,
    deck_id: int,
    new_cards_per_day: Optional[str] = Form(None),
    max_reviews_per_day: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_database)
):
    # Convert empty strings from form to None, otherwise convert to int
    new_cards_val = int(new_cards_per_day) if new_cards_per_day else None
    max_reviews_val = int(max_reviews_per_day) if max_reviews_per_day else None

    crud.update_deck_settings(db, deck_id, new_cards_val, max_reviews_val)
    
    deck = crud.get_deck(db, deck_id) # Re-fetch deck to show updated values
    global_new = crud.get_setting(db, "new_cards_per_day") or "5"
    global_max = crud.get_setting(db, "max_reviews_per_day") or "20"

    return templates.TemplateResponse(
        "settings_deck.html",
        {
            "request": request,
            "deck": deck,
            "global_new_cards_per_day": global_new,
            "global_max_reviews_per_day": global_max,
            "message": "Deck settings updated successfully!"
        }
    )

# Settings endpoints remain for now
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: sqlite3.Connection = Depends(get_database)):
    current_new_cards_per_day = crud.get_setting(db, "new_cards_per_day") or "5"
    current_max_reviews_per_day = crud.get_setting(db, "max_reviews_per_day") or "20"
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "new_cards_per_day": current_new_cards_per_day,
            "max_reviews_per_day": current_max_reviews_per_day,
            "message": None
        }
    )

@app.post("/settings", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    new_cards_per_day: int = Form(...),
    max_reviews_per_day: int = Form(...),
    db: sqlite3.Connection = Depends(get_database)
):
    crud.set_setting(db, "new_cards_per_day", str(new_cards_per_day))
    crud.set_setting(db, "max_reviews_per_day", str(max_reviews_per_day))
    message = "Settings updated successfully!"
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "new_cards_per_day": new_cards_per_day,
            "max_reviews_per_day": max_reviews_per_day,
            "message": message
        }
    )