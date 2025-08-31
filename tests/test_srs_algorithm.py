# tests/test_srs_algorithm.py

import unittest
from unittest.mock import patch
from datetime import datetime, date, timedelta

# This assumes your project root is in the Python path.
# The run_tests.py script handles this.
from app.models import Card
from app.srs_algorithm import sm2_algorithm

class TestSRSAlgorithm(unittest.TestCase):

    def setUp(self):
        """Set up a base card and default settings for each test."""
        self.FROZEN_DATETIME = datetime(2023, 10, 27, 10, 0, 0)
        self.FROZEN_DATE = self.FROZEN_DATETIME.date()

        self.card = Card(
            id=1,
            deck_id=1,
            data={"front": "Q", "back": "A"},
            # Set a past date to ensure it's "due"
            next_review_date=self.FROZEN_DATETIME - timedelta(days=1)
        )
        self.learning_steps = [10, 1440]  # 10 minutes, 1 day
        self.graduating_interval = 4  # 4 days

    @patch('app.srs_algorithm.date')
    @patch('app.srs_algorithm.datetime')
    def test_new_card_rated_good(self, mock_datetime, mock_date):
        """Test a new card being answered correctly for the first time."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        mock_date.today.return_value = self.FROZEN_DATE
        self.card.state = 'new'

        updated_card = sm2_algorithm(self.card, 3, self.learning_steps, self.graduating_interval)

        self.assertEqual(updated_card.state, 'learning')
        self.assertEqual(updated_card.introduction_date, self.FROZEN_DATE)
        self.assertEqual(updated_card.learning_step, 1)
        self.assertEqual(updated_card.reviews, 1)
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(minutes=10))

    @patch('app.srs_algorithm.date')
    @patch('app.srs_algorithm.datetime')
    def test_new_card_rated_incorrect(self, mock_datetime, mock_date):
        """Test a new card being answered incorrectly."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        mock_date.today.return_value = self.FROZEN_DATE
        self.card.state = 'new'

        updated_card = sm2_algorithm(self.card, 1, self.learning_steps, self.graduating_interval)

        self.assertEqual(updated_card.state, 'learning')
        self.assertEqual(updated_card.introduction_date, self.FROZEN_DATE)
        self.assertEqual(updated_card.learning_step, 0) # Step does not advance
        self.assertEqual(updated_card.reviews, 1)
        # It resets to the first learning step
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(minutes=10))

    @patch('app.srs_algorithm.datetime')
    def test_learning_card_graduates(self, mock_datetime):
        """Test a card graduating from 'learning' to 'review'."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'learning'
        self.card.learning_step = 2  # This is the last step

        updated_card = sm2_algorithm(self.card, 3, self.learning_steps, self.graduating_interval)

        self.assertEqual(updated_card.state, 'review')
        self.assertEqual(updated_card.interval_days, self.graduating_interval)
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(days=self.graduating_interval))

    @patch('app.srs_algorithm.datetime')
    def test_review_card_lapse(self, mock_datetime):
        """Test a graduated 'review' card that is answered incorrectly (a lapse)."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'review'
        self.card.interval_days = 20
        self.card.ease_factor = 2.5

        updated_card = sm2_algorithm(self.card, 1, self.learning_steps, self.graduating_interval)

        self.assertEqual(updated_card.state, 'learning')
        self.assertEqual(updated_card.learning_step, 0) # Reset to beginning of learning
        self.assertEqual(updated_card.interval_days, 0)
        self.assertAlmostEqual(updated_card.ease_factor, 2.3) # 2.5 - 0.2 penalty
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(minutes=10))

    @patch('app.srs_algorithm.datetime')
    def test_review_card_good(self, mock_datetime):
        """Test a standard 'review' card answered correctly."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'review'
        self.card.interval_days = 10
        self.card.ease_factor = 2.5

        updated_card = sm2_algorithm(self.card, 3, self.learning_steps, self.graduating_interval)

        new_interval = round(10 * 2.5) # 25
        self.assertEqual(updated_card.state, 'review')
        self.assertEqual(updated_card.interval_days, new_interval)
        self.assertAlmostEqual(updated_card.ease_factor, 2.36)
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(days=new_interval))

    @patch('app.srs_algorithm.datetime')
    def test_review_card_easy(self, mock_datetime):
        """Test a 'review' card answered 'Easy', increasing the ease factor."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'review'
        self.card.interval_days = 10
        self.card.ease_factor = 2.5

        updated_card = sm2_algorithm(self.card, 5, self.learning_steps, self.graduating_interval)

        new_interval = round(10 * 2.5) # 25
        self.assertEqual(updated_card.state, 'review')
        self.assertEqual(updated_card.interval_days, new_interval)
        self.assertAlmostEqual(updated_card.ease_factor, 2.6) # 2.5 + 0.1
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(days=new_interval))

    @patch('app.srs_algorithm.datetime')
    def test_ease_factor_floor(self, mock_datetime):
        """Test that the ease factor does not drop below 1.3."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'review'
        self.card.interval_days = 10
        self.card.ease_factor = 1.35

        # A "good" rating will try to lower the ease factor
        updated_card = sm2_algorithm(self.card, 3, self.learning_steps, self.graduating_interval)
        self.assertEqual(updated_card.ease_factor, 1.3)

        # Try again from the floor
        self.card.ease_factor = 1.3
        updated_card = sm2_algorithm(self.card, 3, self.learning_steps, self.graduating_interval)
        self.assertEqual(updated_card.ease_factor, 1.3)

    @patch('app.srs_algorithm.datetime')
    def test_intermediate_learning_step(self, mock_datetime):
        """Test a correct answer on a card in the middle of learning steps."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'learning'
        self.card.learning_step = 1 # It has completed the first step (10 min)

        # Use a more complex learning step array for this test
        learning_steps = [10, 60, 1440] # 10m, 1h, 1d

        updated_card = sm2_algorithm(self.card, 3, learning_steps, self.graduating_interval)

        self.assertEqual(updated_card.state, 'learning') # Still learning
        self.assertEqual(updated_card.learning_step, 2)   # Advanced to the next step
        # The next review should be 60 minutes from now, as per learning_steps[1]
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(minutes=60))

    @patch('app.srs_algorithm.datetime')
    def test_learning_card_lapse(self, mock_datetime):
        """Test an incorrect answer on a card that is already in the learning state."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'learning'
        self.card.learning_step = 1 # It has already passed the first step

        updated_card = sm2_algorithm(self.card, 1, self.learning_steps, self.graduating_interval)

        self.assertEqual(updated_card.state, 'learning')
        self.assertEqual(updated_card.learning_step, 0) # Reset to the first step
        # Next review is scheduled for the first step's interval
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(minutes=self.learning_steps[0]))

    @patch('app.srs_algorithm.datetime')
    def test_graduation_with_no_learning_steps(self, mock_datetime):
        """Test that a new card graduates immediately if learning_steps is empty."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'new'
        empty_learning_steps = []

        updated_card = sm2_algorithm(self.card, 3, empty_learning_steps, self.graduating_interval)

        self.assertEqual(updated_card.state, 'review') # Should graduate instantly
        self.assertEqual(updated_card.interval_days, self.graduating_interval)
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(days=self.graduating_interval))

    @patch('app.srs_algorithm.datetime')
    def test_first_review_after_graduation(self, mock_datetime):
        """Test the first 'review' state evaluation after graduating."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'review'
        self.card.interval_days = 0 # As it would be right after graduation
        self.card.ease_factor = 2.5

        updated_card = sm2_algorithm(self.card, 3, self.learning_steps, self.graduating_interval)

        self.assertEqual(updated_card.state, 'review')
        # The interval should now be the graduating interval, not 0 * ease_factor
        self.assertEqual(updated_card.interval_days, self.graduating_interval)
        self.assertAlmostEqual(updated_card.ease_factor, 2.36)
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(days=self.graduating_interval))

    @patch('app.srs_algorithm.datetime')
    def test_review_card_quality_4(self, mock_datetime):
        """Test a 'review' card answered with quality=4 ('Good' but better than 3)."""
        mock_datetime.now.return_value = self.FROZEN_DATETIME
        self.card.state = 'review'
        self.card.interval_days = 10
        self.card.ease_factor = 2.5

        # quality=4 is a correct answer
        updated_card = sm2_algorithm(self.card, 4, self.learning_steps, self.graduating_interval)

        new_interval = round(10 * 2.5) # 25
        self.assertEqual(updated_card.state, 'review')
        self.assertEqual(updated_card.interval_days, new_interval)
        
        # The ease factor formula for q=4 is: EF + (0.1 - (5-4)*(0.08+(5-4)*0.02))
        # EF + (0.1 - 1*(0.08+0.02)) = EF + (0.1 - 0.1) = EF + 0
        # So the ease factor should not change.
        self.assertAlmostEqual(updated_card.ease_factor, 2.5)
        self.assertEqual(updated_card.next_review_date, self.FROZEN_DATETIME + timedelta(days=new_interval))