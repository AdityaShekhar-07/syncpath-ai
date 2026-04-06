"""
agents/tools.py — CrewAI-compatible tools wrapping GTFS and ride simulator.

Each tool is a plain callable decorated with @tool so CrewAI agents can
invoke them autonomously during task execution.
"""

import json
from crewai.tools import tool
from gtfs.feed import get_trip_update
from rides.simulator import get_ride_options, get_best_ride

@tool("get_transit_delay")
def get_transit_delay(route_id: str) -> str:
    """
    Fetch the current delay for a metro/train route.
    Input: route_id (e.g. 'YL', 'BL', 'GR')
    Output: JSON string with delay_minutes, current_stop, next_stop.
    """
    update = get_trip_update(route_id=route_id)
    return json.dumps({
        "route_id":      update.route_id,
        "delay_minutes": round(update.delay_minutes, 1),
        "current_stop":  update.current_stop,
        "next_stop":     update.next_stop,
    })

@tool("get_ride_availability")
def get_ride_availability(distance_km: float, demand_factor: float = 1.0) -> str:
    """
    Check ride-hailing availability and surge pricing.
    Input: distance_km (float), demand_factor (float, 1.0=normal, 2.0=high)
    Output: JSON list of available rides with fare and ETA.
    """
    options = get_ride_options(
        distance_km=distance_km,
        duration_min=distance_km * 3,   # rough estimate: 3 min/km
        demand_factor=demand_factor,
    )
    return json.dumps([
        {
            "ride_type":        o.ride_type.value,
            "available":        o.available,
            "surge_multiplier": o.surge_multiplier,
            "total_fare":       o.total_fare,
            "eta_minutes":      o.eta_minutes,
        }
        for o in options
    ])

@tool("get_best_ride_option")
def get_best_ride_option(distance_km: float, prefer_cheap: bool = False) -> str:
    """
    Get the single best ride option.
    Input: distance_km (float), prefer_cheap (bool)
    Output: JSON with best ride details or 'no_rides_available'.
    """
    ride = get_best_ride(
        distance_km=distance_km,
        duration_min=distance_km * 3,
        prefer_cheap=prefer_cheap,
    )
    if ride is None:
        return json.dumps({"status": "no_rides_available"})
    return json.dumps({
        "ride_type":        ride.ride_type.value,
        "total_fare":       ride.total_fare,
        "eta_minutes":      ride.eta_minutes,
        "surge_multiplier": ride.surge_multiplier,
    })
