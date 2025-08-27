from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
from sqlalchemy.orm import Session # We'll use this for type hinting, even with SQLite
import sqlite3
from datetime import date, timedelta

from app import crud, models
from app.database import get_db, create_tables
from app.srs_algorithm import sm2_algorithm # Assuming you put SM-2 here

# Call create_tables once at startup
create_tables()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency to get database connection
def get_database():
    yield from get_db()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: sqlite3.Connection = Depends(get_database)):
    # Redirect to dashboard or study if there are cards to review
    kanji_to_review = crud.get_kanji_for_review(db, date.today())
    if kanji_to_review:
        return RedirectResponse(url="/study")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: sqlite3.Connection = Depends(get_database)):
    all_kanji = crud.get_all_kanji(db)
    kanji_for_review = crud.get_kanji_for_review(db, date.today())
    # Calculate some progress metrics
    total_kanji = len(all_kanji)
    reviewed_kanji = len([k for k in all_kanji if k.reviews > 0])
    mastery_percentage = (reviewed_kanji / total_kanji * 100) if total_kanji > 0 else 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_kanji": total_kanji,
            "kanji_for_review_count": len(kanji_for_review),
            "mastery_percentage": round(mastery_percentage, 1)
        }
    )

@app.get("/study", response_class=HTMLResponse)
async def study_kanji(request: Request, db: sqlite3.Connection = Depends(get_database)):
    kanji_to_review = crud.get_kanji_for_review(db, date.today())

    if not kanji_to_review:
        return templates.TemplateResponse("study.html", {"request": request, "current_kanji": None, "message": "No kanji to review today!"})

    # For simplicity, pick the first one. A real app might have a more complex order.
    current_kanji = kanji_to_review[0]

    return templates.TemplateResponse(
        "study.html",
        {
            "request": request,
            "current_kanji": current_kanji,
            "total_reviews_today": len(kanji_to_review) # Or count remaining
        }
    )

@app.post("/submit_review", response_class=RedirectResponse)
async def submit_review(
    kanji_id: int = Form(...),
    quality: int = Form(...), # 0-2 (Hard), 3 (Good), 4-5 (Easy)
    db: sqlite3.Connection = Depends(get_database)
):
    kanji = crud.get_kanji(db, kanji_id)
    if not kanji:
        return RedirectResponse(url="/study", status_code=303)

    updated_kanji = sm2_algorithm(kanji, quality)
    crud.update_kanji_review_data(
        db, updated_kanji.id, updated_kanji.next_review_date,
        updated_kanji.interval_days, updated_kanji.ease_factor,
        updated_kanji.reviews, updated_kanji.last_reviewed_date
    )
    return RedirectResponse(url="/study", status_code=303)

@app.get("/add_kanji", response_class=HTMLResponse)
async def add_kanji_page(request: Request):
    return templates.TemplateResponse("add_kanji.html", {"request": request, "message": None})

@app.post("/add_kanji", response_class=HTMLResponse)
async def add_kanji_submit(
    request: Request,
    character: str = Form(...),
    meaning: str = Form(...),
    onyomi: Optional[str] = Form(None),
    kunyomi: Optional[str] = Form(None),
    grade: Optional[int] = Form(None),
    stroke_count: Optional[int] = Form(None),
    db: sqlite3.Connection = Depends(get_database)
):
    try:
        new_kanji = models.KanjiCreate(
            character=character,
            meaning=meaning,
            onyomi=onyomi,
            kunyomi=kunyomi,
            grade=grade,
            stroke_count=stroke_count
        )
        crud.create_kanji(db, new_kanji)
        message = f"Kanji '{character}' added successfully!"
    except sqlite3.IntegrityError:
        message = f"Kanji '{character}' already exists."
    except Exception as e:
        message = f"Error adding Kanji: {e}"

    return templates.TemplateResponse("add_kanji.html", {"request": request, "message": message})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: sqlite3.Connection = Depends(get_database)):
    # Retrieve current settings to display them
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

# Import Kanji from file endpoint
@app.post("/import_kanji", response_class=RedirectResponse)
async def import_kanji_file(request: Request, db: sqlite3.Connection = Depends(get_database)):
    # This is a placeholder. You'd implement file upload logic here.
    # For now, let's assume a hardcoded file.
    import json
    try:
        with open("kanji_data/top100_kanji.json", "r", encoding="utf-8") as f:
            kanji_list = json.load(f)

        count = 0
        for item in kanji_list:
            try:
                new_kanji = models.KanjiCreate(
                    character=item['character'],
                    meaning=item['meaning'],
                    onyomi=item.get('onyomi'),
                    kunyomi=item.get('kunyomi'),
                    grade=item.get('grade'),
                    stroke_count=item.get('stroke_count')
                )
                crud.create_kanji(db, new_kanji)
                count += 1
            except sqlite3.IntegrityError:
                # print(f"Kanji '{item['character']}' already exists, skipping.")
                pass # Skip existing kanji
        print(f"Imported {count} new kanji from file.")
        return RedirectResponse(url="/dashboard", status_code=303)
    except FileNotFoundError:
        print("Error: top100_kanji.json not found.")
        return RedirectResponse(url="/add_kanji?error=file_not_found", status_code=303)
    except Exception as e:
        print(f"Error during import: {e}")
        return RedirectResponse(url=f"/add_kanji?error={e}", status_code=303)


@app.get("/progress", response_class=HTMLResponse)
async def progress_page(request: Request, db: sqlite3.Connection = Depends(get_database)):
    # Fetch all kanji to display their current status
    all_kanji = crud.get_all_kanji(db)
    
    # Sort kanji, for example by number of reviews or next review date
    all_kanji_sorted = sorted(all_kanji, key=lambda k: k.next_review_date)

    return templates.TemplateResponse(
        "progress.html",
        {
            "request": request,
            "all_kanji": all_kanji_sorted
        }
    )