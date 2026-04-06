"""
preference_engine.py — Converts user preferences into weights and scores
transport options. Rule-based; no LLM dependency.

Scoring formula (weighted sum, higher = better):
  score = w_time*(1-norm_time) + w_cost*(1-norm_cost)
        + w_comfort*norm_comfort + w_walk*(1-norm_walk)
"""

from dataclasses import dataclass, field
from .models import UserProfile, PrefLevel

# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class TransportOption:
    name:            str          # e.g. "Uber", "Metro+Auto", "Walk"
    travel_time:     float        # minutes
    cost:            float        # INR / local currency
    comfort:         float        # 0–10 scale (10 = most comfortable)
    walking_distance: float       # metres
    available:       bool = True
    extra:           dict = field(default_factory=dict)  # surge, seats, etc.

@dataclass
class ScoredOption:
    option: TransportOption
    score:  float
    rank:   int = 0

# ── Weight mapping ─────────────────────────────────────────────────────────────

_LEVEL_WEIGHT = {PrefLevel.low: 0.5, PrefLevel.medium: 1.0, PrefLevel.high: 2.0}

def _weights(profile: UserProfile) -> dict[str, float]:
    """
    Derive dimension weights from user preferences.
    high urgency  → time matters most
    low budget    → cost matters most
    high comfort  → comfort matters most
    low walking   → walking distance matters most
    """
    w = {
        "time":    _LEVEL_WEIGHT[profile.urgency_level],
        "cost":    _LEVEL_WEIGHT[
                       PrefLevel.high if profile.budget_preference == PrefLevel.low
                       else PrefLevel.low if profile.budget_preference == PrefLevel.high
                       else PrefLevel.medium
                   ],
        "comfort": _LEVEL_WEIGHT[profile.comfort_preference],
        "walk":    _LEVEL_WEIGHT[
                       PrefLevel.high if profile.walking_tolerance == PrefLevel.low
                       else PrefLevel.low if profile.walking_tolerance == PrefLevel.high
                       else PrefLevel.medium
                   ],
    }
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}   # normalise to sum=1

# ── Normalisation helpers ──────────────────────────────────────────────────────

def _norm(values: list[float]) -> list[float]:
    """Min-max normalise; returns 0.0 list if all values are equal."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]

# ── Public API ─────────────────────────────────────────────────────────────────

def rank_options(
    profile: UserProfile,
    options: list[TransportOption],
) -> list[ScoredOption]:
    """
    Score and rank transport options for a given user profile.
    Unavailable options are pushed to the bottom.
    """
    available = [o for o in options if o.available]
    unavailable = [o for o in options if not o.available]

    if not available:
        return [ScoredOption(o, 0.0, i + 1) for i, o in enumerate(unavailable)]

    w = _weights(profile)

    times    = _norm([o.travel_time      for o in available])
    costs    = _norm([o.cost             for o in available])
    comforts = _norm([o.comfort          for o in available])
    walks    = _norm([o.walking_distance for o in available])

    scored = []
    for i, opt in enumerate(available):
        score = (
            w["time"]    * (1 - times[i])    +   # lower time → higher score
            w["cost"]    * (1 - costs[i])    +   # lower cost → higher score
            w["comfort"] * comforts[i]       +   # higher comfort → higher score
            w["walk"]    * (1 - walks[i])        # less walking → higher score
        )
        scored.append(ScoredOption(opt, round(score, 4)))

    scored.sort(key=lambda s: s.score, reverse=True)
    for rank, s in enumerate(scored, start=1):
        s.rank = rank

    # Append unavailable options at the end
    for i, opt in enumerate(unavailable, start=len(scored) + 1):
        scored.append(ScoredOption(opt, 0.0, i))

    return scored
