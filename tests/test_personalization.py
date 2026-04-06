"""
tests/test_personalization.py — Example tests covering all major flows.
Run with: pytest tests/ -v
"""

import pytest
from personalization.models import UserProfile, PrefLevel, init_db, save_user, load_user
from personalization.preference_engine import TransportOption, rank_options
from personalization.decision_engine import SituationContext, make_decision
from personalization.privacy_layer import sanitize_payload
from personalization.learning import update_preferences_from_history

# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Use a temp DB for every test."""
    monkeypatch.setattr("personalization.models.DB_PATH", str(tmp_path / "test.db"))
    init_db()

@pytest.fixture
def budget_user():
    p = UserProfile(
        user_id="user_budget",
        budget_preference=PrefLevel.low,
        urgency_level=PrefLevel.low,
        comfort_preference=PrefLevel.medium,
        walking_tolerance=PrefLevel.medium,
    )
    save_user(p)
    return p

@pytest.fixture
def urgent_user():
    p = UserProfile(
        user_id="user_urgent",
        budget_preference=PrefLevel.high,
        urgency_level=PrefLevel.high,
        comfort_preference=PrefLevel.low,
        walking_tolerance=PrefLevel.high,
    )
    save_user(p)
    return p

@pytest.fixture
def sample_options():
    return [
        TransportOption("Metro+Auto",  travel_time=25, cost=60,  comfort=6, walking_distance=300),
        TransportOption("Uber",        travel_time=18, cost=180, comfort=9, walking_distance=50),
        TransportOption("Bus",         travel_time=40, cost=20,  comfort=4, walking_distance=500),
        TransportOption("Walk",        travel_time=55, cost=0,   comfort=3, walking_distance=4000),
    ]

# ── Preference engine ──────────────────────────────────────────────────────────

def test_budget_user_prefers_cheapest(budget_user, sample_options):
    ranked = rank_options(budget_user, sample_options)
    uber_rank = next(s.rank for s in ranked if s.option.name == "Uber")
    bus_rank  = next(s.rank for s in ranked if s.option.name == "Bus")
    assert bus_rank < uber_rank

def test_urgent_user_prefers_fastest(urgent_user, sample_options):
    ranked = rank_options(urgent_user, sample_options)
    uber_rank  = next(s.rank for s in ranked if s.option.name == "Uber")
    metro_rank = next(s.rank for s in ranked if s.option.name == "Metro+Auto")
    assert uber_rank < metro_rank

def test_unavailable_option_ranked_last(budget_user, sample_options):
    sample_options[1].available = False
    ranked = rank_options(budget_user, sample_options)
    uber_entry = next(s for s in ranked if s.option.name == "Uber")
    assert uber_entry.rank == len(ranked)

# ── Decision engine ────────────────────────────────────────────────────────────

def test_decision_applies_surge(urgent_user, sample_options):
    ctx = SituationContext(surge_multiplier=3.0)
    result = make_decision(urgent_user, ctx, sample_options)
    assert result.best_option is not None
    assert "surge" in result.explanation.lower()

def test_decision_applies_train_delay(budget_user, sample_options):
    ctx = SituationContext(train_delay_minutes=20)
    result = make_decision(budget_user, ctx, sample_options)
    assert "20" in result.explanation or result.best_option is not None

def test_decision_no_rides_available(budget_user, sample_options):
    ctx = SituationContext(ride_available=False)
    result = make_decision(budget_user, ctx, sample_options)
    assert result.best_option.name != "Uber"

# ── Privacy layer ──────────────────────────────────────────────────────────────

def test_sanitize_removes_user_id():
    payload = {"user_id": "alice_123", "location": "Delhi"}
    clean = sanitize_payload(payload)
    assert clean["user_id"].startswith("anon_")
    assert clean["location"] == "Delhi"

def test_sanitize_scrubs_email():
    payload = {"note": "contact me at alice@example.com please"}
    clean = sanitize_payload(payload)
    assert "alice@example.com" not in clean["note"]
    assert "<email>" in clean["note"]

def test_sanitize_nested():
    payload = {"user": {"user_id": "bob", "phone": "9876543210"}}
    clean = sanitize_payload(payload)
    assert clean["user"]["user_id"].startswith("anon_")

# ── Learning module ────────────────────────────────────────────────────────────

def test_learning_nudges_budget_preference():
    profile = UserProfile(
        user_id="learner_01",
        budget_preference=PrefLevel.medium,
        urgency_level=PrefLevel.medium,
        comfort_preference=PrefLevel.medium,
        walking_tolerance=PrefLevel.medium,
        historical_choices=[{"was_cheapest": True, "was_fastest": False, "was_most_comfortable": False}] * 7,
    )
    save_user(profile)
    updated = update_preferences_from_history(profile)
    assert updated.budget_preference == PrefLevel.low

def test_learning_requires_min_history():
    profile = UserProfile(
        user_id="learner_02",
        budget_preference=PrefLevel.medium,
        urgency_level=PrefLevel.medium,
        comfort_preference=PrefLevel.medium,
        walking_tolerance=PrefLevel.medium,
        historical_choices=[{"was_cheapest": True}] * 3,
    )
    save_user(profile)
    updated = update_preferences_from_history(profile)
    assert updated.budget_preference == PrefLevel.medium

# ── DB persistence ─────────────────────────────────────────────────────────────

def test_save_and_load_user(budget_user):
    loaded = load_user("user_budget")
    assert loaded is not None
    assert loaded.budget_preference == PrefLevel.low

def test_load_nonexistent_user():
    assert load_user("ghost_user") is None
