# run_tests.py

import unittest
import sys
import os

# Add the project root to the Python path
# This allows the test runner to find the 'app' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

if __name__ == '__main__':
    # Discover all tests in the 'tests' directory
    loader = unittest.TestLoader()
    suite = loader.discover('tests')

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with a non-zero status code if any tests failed
    if not result.wasSuccessful():
        sys.exit(1)