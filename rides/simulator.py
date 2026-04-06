"""
rides/simulator.py — Simulated ride-hailing availability engine.

Models Uber/Ola/Auto behaviour:
  - Surge pricing based on time-of-day and demand zones
  - Driver availability (pool size simulation)
  - ETA estimation
  - Base fare calculation with per-km rate
"""

import math
import random
import time
from dataclasses import dataclass
from enum import Enum

# ── Enums & constants ──────────────────────────────────────────────────────────

class RideType(str, Enum):
    uber_go    = "Uber Go"
    uber_auto  = "Uber Auto"
    ola_mini   = "Ola Mini"
    ola_auto   = "Ola Auto"
    rapido     = "Rapido Bike"

# Base fares (INR): (base_charge, per_km_rate, per_min_rate)
_FARE_TABLE: dict[RideType, tuple[float, float, float]] = {
    RideType.uber_go:   (50.0, 12.0, 1.5),
    RideType.uber_auto: (30.0,  8.0, 1.0),
    RideType.ola_mini:  (45.0, 11.0, 1.4),
    RideType.ola_auto:  (25.0,  7.5, 0.9),
    RideType.rapido:    (20.0,  5.0, 0.8),
}

# Peak hours drive surge
_PEAK_HOURS = {8, 9, 17, 18, 19}   # 8-9 AM, 5-7 PM

# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class RideOption:
    ride_type:        RideType
    available:        bool
    surge_multiplier: float
    base_fare:        float          # INR before surge
    total_fare:       float          # INR after surge
    eta_minutes:      float          # driver ETA
    drivers_nearby:   int

# ── Internal helpers ───────────────────────────────────────────────────────────

def _current_surge(ride_type: RideType, demand_factor: float = 1.0) -> float:
    """
    Compute surge multiplier.
    Peak hours + high demand → higher surge.
    Rapido bikes have lower surge ceiling.
    """
    hour = time.localtime().tm_hour
    base_surge = 1.5 if hour in _PEAK_HOURS else 1.0
    surge = base_surge * demand_factor
    # Bikes cap at 1.5x, cabs cap at 3.0x
    cap = 1.5 if ride_type == RideType.rapido else 3.0
    return round(min(surge, cap), 2)

def _estimate_fare(ride_type: RideType, distance_km: float, duration_min: float, surge: float) -> float:
    base, per_km, per_min = _FARE_TABLE[ride_type]
    fare = (base + per_km * distance_km + per_min * duration_min) * surge
    return round(fare, 2)

def _drivers_nearby(ride_type: RideType, demand_factor: float) -> int:
    """Simulate driver pool size — inversely proportional to demand."""
    base = {
        RideType.uber_go: 8, RideType.uber_auto: 12,
        RideType.ola_mini: 6, RideType.ola_auto: 10,
        RideType.rapido: 15,
    }[ride_type]
    count = max(0, int(base / demand_factor + random.gauss(0, 1)))
    return count

# ── Public API ─────────────────────────────────────────────────────────────────

def get_ride_options(
    distance_km:   float = 5.0,
    duration_min:  float = 20.0,
    demand_factor: float = 1.0,    # 1.0 = normal, 2.0 = high demand
) -> list[RideOption]:
    """
    Return availability + pricing for all ride types.
    demand_factor > 1 simulates high-demand zones (airports, events).
    """
    options = []
    for ride_type in RideType:
        surge    = _current_surge(ride_type, demand_factor)
        drivers  = _drivers_nearby(ride_type, demand_factor)
        available = drivers > 0
        base_fare = _estimate_fare(ride_type, distance_km, duration_min, 1.0)
        total_fare = _estimate_fare(ride_type, distance_km, duration_min, surge)
        # ETA: fewer drivers → longer wait
        eta = round(max(2.0, 15.0 / max(drivers, 1) + random.uniform(0, 3)), 1)

        options.append(RideOption(
            ride_type        = ride_type,
            available        = available,
            surge_multiplier = surge,
            base_fare        = base_fare,
            total_fare       = total_fare,
            eta_minutes      = eta,
            drivers_nearby   = drivers,
        ))
    return options

def get_best_ride(
    distance_km:   float = 5.0,
    duration_min:  float = 20.0,
    demand_factor: float = 1.0,
    prefer_cheap:  bool  = False,
) -> RideOption | None:
    """Return the best available ride — fastest ETA by default, cheapest if prefer_cheap."""
    options = [o for o in get_ride_options(distance_km, duration_min, demand_factor) if o.available]
    if not options:
        return None
    key = (lambda o: o.total_fare) if prefer_cheap else (lambda o: o.eta_minutes)
    return min(options, key=key)
