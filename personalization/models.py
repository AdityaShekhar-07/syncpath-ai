"""
models.py — User profile schema (Pydantic) + SQLite persistence layer.
All data stays local; no external writes.
"""

import json
import sqlite3
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

DB_PATH = "syncpath_users.db"

# ── Enums ──────────────────────────────────────────────────────────────────────

class PrefLevel(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"

# ── Pydantic schemas ───────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    user_id:            str
    budget_preference:  PrefLevel = PrefLevel.medium
    urgency_level:      PrefLevel = PrefLevel.medium
    comfort_preference: PrefLevel = PrefLevel.medium
    walking_tolerance:  PrefLevel = PrefLevel.medium
    historical_choices: list[dict] = Field(default_factory=list)

class UserCreateRequest(BaseModel):
    user_id:            str
    budget_preference:  PrefLevel = PrefLevel.medium
    urgency_level:      PrefLevel = PrefLevel.medium
    comfort_preference: PrefLevel = PrefLevel.medium
    walking_tolerance:  PrefLevel = PrefLevel.medium

class UpdatePreferencesRequest(BaseModel):
    user_id:            str
    budget_preference:  Optional[PrefLevel] = None
    urgency_level:      Optional[PrefLevel] = None
    comfort_preference: Optional[PrefLevel] = None
    walking_tolerance:  Optional[PrefLevel] = None

# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Create the users table if it doesn't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id            TEXT PRIMARY KEY,
                budget_preference  TEXT NOT NULL DEFAULT 'medium',
                urgency_level      TEXT NOT NULL DEFAULT 'medium',
                comfort_preference TEXT NOT NULL DEFAULT 'medium',
                walking_tolerance  TEXT NOT NULL DEFAULT 'medium',
                historical_choices TEXT NOT NULL DEFAULT '[]'
            )
        """)

def save_user(profile: UserProfile) -> None:
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO users VALUES (?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                budget_preference  = excluded.budget_preference,
                urgency_level      = excluded.urgency_level,
                comfort_preference = excluded.comfort_preference,
                walking_tolerance  = excluded.walking_tolerance,
                historical_choices = excluded.historical_choices
        """, (
            profile.user_id,
            profile.budget_preference,
            profile.urgency_level,
            profile.comfort_preference,
            profile.walking_tolerance,
            json.dumps(profile.historical_choices),
        ))

def load_user(user_id: str) -> Optional[UserProfile]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return None
    return UserProfile(
        user_id            = row["user_id"],
        budget_preference  = row["budget_preference"],
        urgency_level      = row["urgency_level"],
        comfort_preference = row["comfort_preference"],
        walking_tolerance  = row["walking_tolerance"],
        historical_choices = json.loads(row["historical_choices"]),
    )

def append_history(user_id: str, choice: dict) -> None:
    """Append a single decision record to the user's history."""
    profile = load_user(user_id)
    if profile is None:
        return
    profile.historical_choices.append(choice)
    # Keep only the last 50 decisions to avoid unbounded growth
    profile.historical_choices = profile.historical_choices[-50:]
    save_user(profile)
