"""Test configuration — ensure app is importable from tests directory."""

import os
import sys

# Add model-server directory to Python path so `from app import ...` works
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
