from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import json
from datetime import date
from typing import Optional, Dict, Any

from app import crud, models
from app.database import get_db, create_tables


# Call create_tables once at startup
create_tables()

app = FastAPI()

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
@app.get("/study/{deck_id}", response_class=HTMLResponse)
async def study_deck(request: Request, deck_id: int, db: sqlite3.Connection = Depends(get_database)):
    deck = crud.get_deck(db, deck_id)
    if not deck:
        return RedirectResponse(url="/decks")

    # --- SETTINGS LOGIC ---
    # Get global settings as fallbacks
    global_max_reviews = int(crud.get_setting(db, "max_reviews_per_day") or "20")
    # Determine the effective setting: deck-specific, or global if not set
    effective_max_reviews = deck.max_reviews_per_day or global_max_reviews
    
    # Use the effective setting in the CRUD call
    cards_to_review = crud.get_cards_for_review(db, deck_id, date.today(), limit=effective_max_reviews)
    
    # (The rest of the function is the same...)
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

@app.post("/submit_review/{deck_id}", response_class=RedirectResponse)
async def submit_review(
    deck_id: int,
    card_id: int = Form(...),
    quality: int = Form(...),
    db: sqlite3.Connection = Depends(get_database)
):
    from app.srs_algorithm import sm2_algorithm

    card = crud.get_card(db, card_id)
    if not card:
        return RedirectResponse(url=f"/study/{deck_id}", status_code=303)

    # Use the existing SRS algorithm
    updated_card = sm2_algorithm(card, quality)
    
    # Persist the changes to the database
    crud.update_card_review_data(
        db, updated_card.id, updated_card.next_review_date,
        updated_card.interval_days, updated_card.ease_factor,
        updated_card.reviews, updated_card.last_reviewed_date
    )

    # Redirect back to the study page for the same deck to get the next card
    return RedirectResponse(url=f"/study/{deck_id}", status_code=303)


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