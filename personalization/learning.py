"""
learning.py — Lightweight preference updater (Bonus).

After each accepted decision, nudge the user's preference weights toward
the attributes of the chosen option using an exponential moving average.

No ML library required — pure arithmetic.
"""

from collections import Counter
from .models import UserProfile, PrefLevel, save_user

_LEVELS = [PrefLevel.low, PrefLevel.medium, PrefLevel.high]
_LEVEL_IDX = {l: i for i, l in enumerate(_LEVELS)}

def _nudge(current: PrefLevel, direction: int) -> PrefLevel:
    """Shift a PrefLevel one step in direction (+1 up, -1 down), clamped."""
    idx = _LEVEL_IDX[current] + direction
    return _LEVELS[max(0, min(2, idx))]

def update_preferences_from_history(profile: UserProfile) -> UserProfile:
    """
    Analyse the last N choices and nudge preferences if a clear pattern exists.

    Heuristics:
      - If user repeatedly chose the cheapest option → nudge budget to 'low'
      - If user repeatedly chose the fastest option  → nudge urgency to 'high'
      - If user repeatedly chose highest comfort     → nudge comfort to 'high'
    Requires at least 5 historical choices to act.
    """
    history = profile.historical_choices[-10:]   # look at last 10 decisions
    if len(history) < 5:
        return profile                            # not enough data yet

    chosen_attrs = Counter()
    for choice in history:
        if choice.get("was_cheapest"):
            chosen_attrs["cheap"] += 1
        if choice.get("was_fastest"):
            chosen_attrs["fast"] += 1
        if choice.get("was_most_comfortable"):
            chosen_attrs["comfort"] += 1

    threshold = len(history) * 0.6   # 60 % of recent choices show the pattern

    if chosen_attrs["cheap"] >= threshold:
        profile.budget_preference = _nudge(profile.budget_preference, -1)  # toward low

    if chosen_attrs["fast"] >= threshold:
        profile.urgency_level = _nudge(profile.urgency_level, +1)           # toward high

    if chosen_attrs["comfort"] >= threshold:
        profile.comfort_preference = _nudge(profile.comfort_preference, +1) # toward high

    save_user(profile)
    return profile
