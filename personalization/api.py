"""
api.py — FastAPI router for the personalization module.

Endpoints:
  POST /create-user
  GET  /get-profile/{user_id}
  POST /update-preferences
  POST /get-decision
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .models import (
    UserProfile, UserCreateRequest, UpdatePreferencesRequest,
    load_user, save_user, append_history,
)
from .preference_engine import TransportOption
from .decision_engine import SituationContext, make_decision
from .llm_integration import refine_explanation
from .learning import update_preferences_from_history

router = APIRouter(prefix="/personalization", tags=["Personalization"])

# ── Request / Response schemas ─────────────────────────────────────────────────

class TransportOptionIn(BaseModel):
    name:             str
    travel_time:      float
    cost:             float
    comfort:          float
    walking_distance: float
    available:        bool = True

class SituationIn(BaseModel):
    train_delay_minutes: float = 0.0
    surge_multiplier:    float = 1.0
    ride_available:      bool  = True
    weather_bad:         bool  = False

class DecisionRequest(BaseModel):
    user_id:  str
    situation: SituationIn
    options:  list[TransportOptionIn]
    use_llm:  bool = False   # opt-in LLM refinement

class DecisionResponse(BaseModel):
    best_option:  str
    explanation:  str
    score:        float
    ranked:       list[dict]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_or_404(user_id: str) -> UserProfile:
    profile = load_user(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")
    return profile

# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/create-user", response_model=UserProfile, status_code=201)
def create_user(req: UserCreateRequest):
    """Create a new user profile and persist it locally."""
    if load_user(req.user_id):
        raise HTTPException(status_code=409, detail="User already exists.")
    profile = UserProfile(**req.model_dump())
    save_user(profile)
    return profile


@router.get("/get-profile/{user_id}", response_model=UserProfile)
def get_profile(user_id: str):
    """Retrieve a user profile by ID."""
    return _get_or_404(user_id)


@router.post("/update-preferences", response_model=UserProfile)
def update_preferences(req: UpdatePreferencesRequest):
    """Partially update user preference fields."""
    profile = _get_or_404(req.user_id)
    updates = req.model_dump(exclude_unset=True, exclude={"user_id"})
    for field, value in updates.items():
        setattr(profile, field, value)
    save_user(profile)
    return profile


@router.post("/get-decision", response_model=DecisionResponse)
def get_decision(req: DecisionRequest):
    """
    Core decision endpoint.
    Scores options, picks the best one, returns explanation.
    Optionally refines explanation via local Ollama LLM.
    """
    profile = _get_or_404(req.user_id)

    options = [TransportOption(**o.model_dump()) for o in req.options]
    context = SituationContext(**req.situation.model_dump())

    llm_fn = refine_explanation if req.use_llm else None
    result = make_decision(profile, context, options, llm_refine_fn=llm_fn)

    # Record this decision in history for the learning module
    best = result.best_option
    ranked_costs  = sorted(options, key=lambda o: o.cost)
    ranked_times  = sorted(options, key=lambda o: o.travel_time)
    ranked_comf   = sorted(options, key=lambda o: o.comfort, reverse=True)

    append_history(req.user_id, {
        "chosen":               best.name,
        "was_cheapest":         best.name == ranked_costs[0].name,
        "was_fastest":          best.name == ranked_times[0].name,
        "was_most_comfortable": best.name == ranked_comf[0].name,
    })

    # Nudge preferences based on updated history (learning module)
    updated_profile = load_user(req.user_id)
    if updated_profile:
        update_preferences_from_history(updated_profile)

    return DecisionResponse(
        best_option = best.name,
        explanation = result.explanation,
        score       = result.score,
        ranked      = [
            {"rank": s.rank, "name": s.option.name, "score": s.score, "available": s.option.available}
            for s in result.ranked_list
        ],
    )
