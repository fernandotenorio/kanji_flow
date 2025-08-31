# tests/test_crud.py

import unittest
import sqlite3
import json
from unittest.mock import patch
from datetime import datetime, date, timedelta

# This assumes your project root is in the Python path.
from app import crud, models
from app.database import create_tables

class TestCRUD(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory database for each test."""
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        # Create tables from the schema in database.py
        create_tables_sql = """
        CREATE TABLE decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, card_template TEXT NOT NULL,
            card_css TEXT NOT NULL, media_folder TEXT, new_cards_per_day INTEGER, max_reviews_per_day INTEGER,
            learning_steps TEXT, graduating_interval INTEGER
        );
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, deck_id INTEGER NOT NULL, data TEXT NOT NULL,
            next_review_date TEXT, interval_days REAL DEFAULT 0.0, ease_factor REAL DEFAULT 2.5,
            reviews INTEGER DEFAULT 0, last_reviewed_date TEXT, state TEXT NOT NULL DEFAULT 'new',
            learning_step INTEGER NOT NULL DEFAULT 0, introduction_date TEXT,
            FOREIGN KEY(deck_id) REFERENCES decks(id) ON DELETE CASCADE
        );
        CREATE TABLE review_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, deck_id INTEGER NOT NULL, card_id INTEGER NOT NULL,
            review_timestamp TEXT NOT NULL, quality INTEGER NOT NULL,
            FOREIGN KEY(deck_id) REFERENCES decks(id) ON DELETE CASCADE,
            FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
        );
        """
        self.db.executescript(create_tables_sql)

        # Create a sample deck for card tests
        self.deck1 = crud.create_deck(self.db, models.DeckCreate(name="Deck 1", card_template="t", card_css="c"))

    def tearDown(self):
        """Close the database connection after each test."""
        self.db.close()

    # --- Deck Tests ---
    def test_create_and_get_deck(self):
        deck_model = models.DeckCreate(name="Test Deck", card_template="<p>Q</p>", card_css="p {color: red;}")
        created_deck = crud.create_deck(self.db, deck_model)
        self.assertIsNotNone(created_deck.id)
        self.assertEqual(created_deck.name, "Test Deck")

        retrieved_deck = crud.get_deck(self.db, created_deck.id)
        self.assertEqual(retrieved_deck.id, created_deck.id)

    def test_delete_deck_cascades(self):
        """Test that deleting a deck also deletes its cards."""
        card_model = models.CardCreate(deck_id=self.deck1.id, data={"q": "a"})
        created_card = crud.create_card(self.db, card_model)
        self.assertIsNotNone(crud.get_card(self.db, created_card.id))

        crud.delete_deck(self.db, self.deck1.id)
        self.assertIsNone(crud.get_deck(self.db, self.deck1.id))
        self.assertIsNone(crud.get_card(self.db, created_card.id))

    # --- Card Tests ---
    def test_create_and_get_card(self):
        card_model = models.CardCreate(deck_id=self.deck1.id, data={"question": "What is FastAPI?", "answer": "A framework."})
        created_card = crud.create_card(self.db, card_model)
        self.assertIsNotNone(created_card.id)
        self.assertEqual(created_card.deck_id, self.deck1.id)
        self.assertEqual(created_card.data["question"], "What is FastAPI?")

        retrieved_card = crud.get_card(self.db, created_card.id)
        self.assertEqual(retrieved_card.id, created_card.id)

    # --- Queue and Review Logic Tests ---
    @patch('app.crud.date')
    @patch('app.crud.datetime')
    def test_get_next_card_for_review_priority(self, mock_datetime, mock_date):
        """Test the priority: Learning > Review > New."""
        FROZEN_TIME = datetime(2023, 10, 27, 12, 0, 0)
        mock_datetime.now.return_value = FROZEN_TIME
        mock_date.today.return_value = FROZEN_TIME.date()

        # 1. Create a "New" card (lowest priority)
        new_card = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "new"}))
        new_card.state = 'new'
        crud.update_card_review_data(self.db, new_card)

        # 2. Create a "Review" card due today (medium priority)
        review_card_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "review"}))
        review_card_model.state = 'review'
        review_card_model.next_review_date = FROZEN_TIME - timedelta(days=1)
        review_card = crud.update_card_review_data(self.db, review_card_model)

        # 3. Create a "Learning" card due now (highest priority)
        learning_card_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "learning"}))
        learning_card_model.state = 'learning'
        learning_card_model.next_review_date = FROZEN_TIME - timedelta(minutes=5)
        learning_card = crud.update_card_review_data(self.db, learning_card_model)

        # Fetch next card - should be the learning card
        next_card = crud.get_next_card_for_review(self.db, self.deck1.id, new_card_limit=5, total_limit=20)
        self.assertEqual(next_card.id, learning_card.id)

        # "Review" the learning card so it's no longer due
        learning_card.next_review_date = FROZEN_TIME + timedelta(minutes=10)
        crud.update_card_review_data(self.db, learning_card)

        # Fetch next card - should be the review card
        next_card = crud.get_next_card_for_review(self.db, self.deck1.id, new_card_limit=5, total_limit=20)
        self.assertEqual(next_card.id, review_card.id)

        # "Review" the review card
        review_card.next_review_date = FROZEN_TIME + timedelta(days=5)
        crud.update_card_review_data(self.db, review_card)

        # Fetch next card - should be the new card
        next_card = crud.get_next_card_for_review(self.db, self.deck1.id, new_card_limit=5, total_limit=20)
        self.assertEqual(next_card.id, new_card.id)

    @patch('app.crud.date')
    def test_get_next_card_new_limit_reached(self, mock_date):
        """Test that no new card is returned if the daily limit is met."""
        FROZEN_DATE = date(2023, 10, 27)
        mock_date.today.return_value = FROZEN_DATE

        # Create one new card and mark it as "introduced today"
        card_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "new 1"}))
        card_model.introduction_date = FROZEN_DATE
        crud.update_card_review_data(self.db, card_model)

        # Create a second, un-introduced new card
        crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "new 2"}))

        # Set the new card limit to 1. Since one was already introduced, we should get None.
        next_card = crud.get_next_card_for_review(self.db, self.deck1.id, new_card_limit=1, total_limit=20)
        self.assertIsNone(next_card)

    @patch('app.crud.date')
    def test_get_reviews_done_today(self, mock_date):
        """Test the daily review counter."""
        FROZEN_TIME = datetime(2023, 10, 27, 12, 0, 0)
        mock_date.today.return_value = FROZEN_TIME.date()

        card = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"q": "a"}))

        with patch('app.crud.datetime') as mock_datetime:
            # Log two reviews "today"
            mock_datetime.now.return_value = FROZEN_TIME
            crud.log_review(self.db, self.deck1.id, card.id, 3)
            mock_datetime.now.return_value = FROZEN_TIME + timedelta(minutes=1)
            crud.log_review(self.db, self.deck1.id, card.id, 3)

            # Log one review "yesterday"
            mock_datetime.now.return_value = FROZEN_TIME - timedelta(days=1)
            crud.log_review(self.db, self.deck1.id, card.id, 3)

        count = crud.get_reviews_done_today(self.db, self.deck1.id)
        self.assertEqual(count, 2)

    @patch('app.crud.datetime')
    def test_get_next_card_ordering_within_queue(self, mock_datetime):
        """Test that the card due earliest is returned first."""
        FROZEN_TIME = datetime(2023, 10, 27, 12, 0, 0)
        mock_datetime.now.return_value = FROZEN_TIME

        # Card due 10 minutes ago (should be picked second)
        card_model_2 = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "2"}))
        card_model_2.state = 'learning'
        card_model_2.next_review_date = FROZEN_TIME - timedelta(minutes=10)
        crud.update_card_review_data(self.db, card_model_2)

        # Card due 20 minutes ago (should be picked first)
        card_model_1 = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "1"}))
        card_model_1.state = 'learning'
        card_model_1.next_review_date = FROZEN_TIME - timedelta(minutes=20)
        card1 = crud.update_card_review_data(self.db, card_model_1)

        next_card = crud.get_next_card_for_review(self.db, self.deck1.id, 5, 20)
        self.assertEqual(next_card.id, card1.id)

    @patch('app.crud.date')
    def test_get_next_card_review_date_boundary(self, mock_date):
        """Test that a review card due yesterday is available today."""
        FROZEN_DATE = date(2023, 10, 27)
        mock_date.today.return_value = FROZEN_DATE

        # Card due just before midnight yesterday. Should be available.
        card_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "due"}))
        card_model.state = 'review'
        card_model.next_review_date = datetime(2023, 10, 26, 23, 59, 59)
        due_card = crud.update_card_review_data(self.db, card_model)

        # Card due just after midnight tomorrow. Should NOT be available.
        card_model_future = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "future"}))
        card_model_future.state = 'review'
        card_model_future.next_review_date = datetime(2023, 10, 28, 0, 0, 1)
        crud.update_card_review_data(self.db, card_model_future)

        next_card = crud.get_next_card_for_review(self.db, self.deck1.id, 5, 20)
        self.assertIsNotNone(next_card)
        self.assertEqual(next_card.id, due_card.id)

    def test_get_next_card_when_none_are_due(self):
        """Test that None is returned when no cards are due for review."""
        now = datetime.now()
        # Create cards that are not due yet
        card_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "1"}))
        card_model.state = 'review'
        card_model.next_review_date = now + timedelta(days=1)
        crud.update_card_review_data(self.db, card_model)

        card_model_2 = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "2"}))
        card_model_2.state = 'learning'
        card_model_2.next_review_date = now + timedelta(minutes=10)
        crud.update_card_review_data(self.db, card_model_2)

        next_card = crud.get_next_card_for_review(self.db, self.deck1.id, 5, 20)
        self.assertIsNone(next_card)

    def test_foreign_key_constraint(self):
        """Test that creating a card for a non-existent deck fails."""
        non_existent_deck_id = 999
        card_model = models.CardCreate(deck_id=non_existent_deck_id, data={"q": "a"})
        
        # This action should violate the FOREIGN KEY constraint and raise an IntegrityError.
        with self.assertRaises(sqlite3.IntegrityError):
            crud.create_card(self.db, card_model)

    @patch('app.crud.date')
    @patch('app.crud.datetime')
    def test_get_queue_counts(self, mock_datetime, mock_date):
        """Verify the accuracy of the queue counting logic."""
        FROZEN_TIME = datetime(2023, 10, 27, 12, 0, 0)
        mock_datetime.now.return_value = FROZEN_TIME
        mock_date.today.return_value = FROZEN_TIME.date()

        # 1. New card (should be counted)
        crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "new"}))

        # 2. Learning card due now (should be counted)
        learning_due_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "learn_due"}))
        learning_due_model.state = 'learning'
        learning_due_model.next_review_date = FROZEN_TIME - timedelta(minutes=1)
        crud.update_card_review_data(self.db, learning_due_model)

        # 3. Learning card due in the future (should NOT be counted)
        learning_future_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "learn_future"}))
        learning_future_model.state = 'learning'
        learning_future_model.next_review_date = FROZEN_TIME + timedelta(minutes=1)
        crud.update_card_review_data(self.db, learning_future_model)

        # 4. Review card due yesterday (should be counted)
        review_due_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "review_due"}))
        review_due_model.state = 'review'
        review_due_model.next_review_date = FROZEN_TIME - timedelta(days=1)
        crud.update_card_review_data(self.db, review_due_model)

        # 5. Review card due tomorrow (should NOT be counted)
        review_future_model = crud.create_card(self.db, models.CardCreate(deck_id=self.deck1.id, data={"card": "review_future"}))
        review_future_model.state = 'review'
        review_future_model.next_review_date = FROZEN_TIME + timedelta(days=1)
        crud.update_card_review_data(self.db, review_future_model)
        
        # The new card limit doesn't affect the count of available new cards.
        counts = crud.get_queue_counts(self.db, self.deck1.id, new_card_limit=5)
        
        self.assertEqual(counts['new'], 1)
        self.assertEqual(counts['learning'], 1)
        self.assertEqual(counts['review'], 1)