"""
personalization/__init__.py
Initialises the SQLite database when the package is first imported.
"""
from .models import init_db

init_db()
