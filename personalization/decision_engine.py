"""
decision_engine.py — Combines user profile + live situation + ranked options
to produce a final decision with a rule-based explanation.

LLM is called ONLY to polish the explanation string (optional, non-blocking).
"""

from dataclasses import dataclass
from .models import UserProfile, PrefLevel
from .preference_engine import TransportOption, ScoredOption, rank_options

# ── Situation context ──────────────────────────────────────────────────────────

@dataclass
class SituationContext:
    train_delay_minutes: float = 0.0   # 0 = on time
    surge_multiplier:    float = 1.0   # 1.0 = no surge
    ride_available:      bool  = True
    weather_bad:         bool  = False

# ── Decision result ────────────────────────────────────────────────────────────

@dataclass
class DecisionResult:
    best_option:  TransportOption
    explanation:  str
    ranked_list:  list[ScoredOption]
    score:        float

# ── Situation adjustments ──────────────────────────────────────────────────────

def _apply_situation(
    options: list[TransportOption],
    ctx: SituationContext,
) -> list[TransportOption]:
    """
    Mutate option costs/times/availability based on live situation.
    Returns new list (originals unchanged).
    """
    adjusted = []
    for opt in options:
        o = TransportOption(**vars(opt))   # shallow copy
        name_lower = o.name.lower()

        # Apply surge to ride-hailing options
        if any(k in name_lower for k in ("uber", "ola", "cab", "ride", "auto")):
            o.cost *= ctx.surge_multiplier
            if not ctx.ride_available:
                o.available = False

        # Add train delay to transit options
        if any(k in name_lower for k in ("metro", "train", "rail", "transit")):
            o.travel_time += ctx.train_delay_minutes

        # Walking is less comfortable in bad weather
        if ctx.weather_bad and "walk" in name_lower:
            o.comfort = max(0.0, o.comfort - 3.0)

        adjusted.append(o)
    return adjusted

# ── Explanation builder ────────────────────────────────────────────────────────

def _build_explanation(
    profile: UserProfile,
    ctx: SituationContext,
    best: ScoredOption,
    ranked: list[ScoredOption],
) -> str:
    reasons = []

    if profile.urgency_level == PrefLevel.high:
        reasons.append("your high urgency prioritises fastest travel time")
    if profile.budget_preference == PrefLevel.low:
        reasons.append("your low budget preference minimises cost")
    if ctx.surge_multiplier > 1.5:
        reasons.append(f"surge pricing ({ctx.surge_multiplier:.1f}x) penalised ride-hailing options")
    if ctx.train_delay_minutes > 0:
        reasons.append(f"train delay of {ctx.train_delay_minutes:.0f} min was factored in")
    if not ctx.ride_available:
        reasons.append("no rides were available at this time")

    reason_str = "; ".join(reasons) if reasons else "balanced scoring across time, cost, comfort, and walking"

    alternatives = [s.option.name for s in ranked[1:3] if s.option.available]
    alt_str = f" Alternatives: {', '.join(alternatives)}." if alternatives else ""

    return (
        f"Recommended '{best.option.name}' (score {best.score:.2f}) because {reason_str}."
        f"{alt_str}"
    )

# ── Public API ─────────────────────────────────────────────────────────────────

def make_decision(
    profile: UserProfile,
    context: SituationContext,
    options: list[TransportOption],
    llm_refine_fn=None,          # optional callable(explanation: str) -> str
) -> DecisionResult:
    """
    Core decision function.
    1. Adjust options for live situation.
    2. Score & rank via preference engine.
    3. Build rule-based explanation.
    4. Optionally refine explanation with LLM (non-blocking).
    """
    adjusted = _apply_situation(options, context)
    ranked   = rank_options(profile, adjusted)

    best = ranked[0]
    explanation = _build_explanation(profile, context, best, ranked)

    # LLM refinement is optional — if it fails, we keep the rule-based text
    if llm_refine_fn:
        try:
            explanation = llm_refine_fn(explanation)
        except Exception:
            pass   # silently fall back to rule-based explanation

    return DecisionResult(
        best_option = best.option,
        explanation = explanation,
        ranked_list = ranked,
        score       = best.score,
    )
