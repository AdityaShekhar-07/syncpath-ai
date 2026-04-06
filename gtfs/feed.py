"""
gtfs/feed.py — Live GTFS-RT trip update poller with simulated fallback.

Real feeds (e.g. Delhi Metro, BMTC) publish protobuf over HTTP.
We parse them with the `gtfs-realtime-bindings` library when available,
and fall back to a deterministic simulation so the rest of the system
always has data to work with.
"""

import random
import time
from dataclasses import dataclass, field
from typing import Optional

# Optional: real GTFS-RT parsing (pip install gtfs-realtime-bindings)
try:
    from google.transit import gtfs_realtime_pb2
    import httpx
    _GTFS_RT_AVAILABLE = True
except ImportError:
    _GTFS_RT_AVAILABLE = False

# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class TripUpdate:
    trip_id:          str
    route_id:         str
    delay_seconds:    int          # positive = late, negative = early
    current_stop:     str
    next_stop:        str
    timestamp:        float = field(default_factory=time.time)

    @property
    def delay_minutes(self) -> float:
        return self.delay_seconds / 60

# ── Simulated feed (always available) ─────────────────────────────────────────

# Realistic Delhi Metro / Bangalore Metro route stubs
_SIM_ROUTES = [
    {"route_id": "YL",  "stops": ["Samaypur Badli", "Rohini Sec-18", "Haiderpur", "Jahangirpuri", "Adarsh Nagar", "Azadpur", "Model Town", "GTB Nagar", "Vishwavidyalaya", "Vidhan Sabha", "Civil Lines", "Kashmere Gate"]},
    {"route_id": "BL",  "stops": ["Dwarka Sec-21", "Dwarka Sec-8", "Dwarka", "Dwarka Mor", "Uttam Nagar West", "Uttam Nagar East", "Janakpuri West", "Janakpuri East", "Tilak Nagar", "Subhash Nagar", "Tagore Garden", "Rajouri Garden", "Ramesh Nagar", "Moti Nagar", "Kirti Nagar", "Shadipur", "Patel Nagar", "Rajendra Place", "Karol Bagh", "Jhandewalan", "RK Ashram Marg", "Rajiv Chowk", "Barakhamba Road", "Mandi House", "Pragati Maidan", "Indraprastha", "Yamuna Bank", "Laxmi Nagar", "Nirman Vihar", "Preet Vihar", "Karkarduma", "Anand Vihar", "Kaushambi", "Vaishali"]},
    {"route_id": "GR",  "stops": ["Inderlok", "Ashok Park Main", "Punjabi Bagh West", "ESI Hospital", "Rajouri Garden", "Madipur", "Paschim Vihar East", "Paschim Vihar West", "Peeragarhi", "Udyog Nagar", "Surajmal Stadium", "Nangloi", "Nangloi Railway Station", "Rajdhani Park", "Mundka", "Mundka Industrial Area", "Ghevra", "Tikri Kalan", "Tikri Border", "Pandit Shree Ram Sharma", "Bahadurgarh City", "Brigadier Hoshiyar Singh"]},
]

def _simulate_trip_update(route_id: Optional[str] = None) -> TripUpdate:
    """Generate a plausible simulated trip update."""
    route = (
        next((r for r in _SIM_ROUTES if r["route_id"] == route_id), None)
        or random.choice(_SIM_ROUTES)
    )
    stops = route["stops"]
    idx   = random.randint(0, len(stops) - 2)

    # Simulate realistic delay distribution: mostly on-time, occasional delays
    delay_seconds = int(random.choices(
        [0, random.randint(60, 180), random.randint(180, 600), random.randint(600, 1200)],
        weights=[50, 25, 15, 10],
    )[0])

    return TripUpdate(
        trip_id       = f"{route['route_id']}-{random.randint(100, 999)}",
        route_id      = route["route_id"],
        delay_seconds = delay_seconds,
        current_stop  = stops[idx],
        next_stop     = stops[idx + 1],
    )

# ── Live GTFS-RT fetch ─────────────────────────────────────────────────────────

def _fetch_live(feed_url: str, route_id: Optional[str]) -> Optional[TripUpdate]:
    """
    Fetch and parse a real GTFS-RT protobuf feed.
    Returns None if parsing fails or library is missing.
    """
    if not _GTFS_RT_AVAILABLE:
        return None
    try:
        resp = httpx.get(feed_url, timeout=5)
        resp.raise_for_status()
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(resp.content)
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            tu = entity.trip_update
            if route_id and tu.trip.route_id != route_id:
                continue
            if tu.stop_time_update:
                delay = tu.stop_time_update[0].departure.delay
                return TripUpdate(
                    trip_id       = tu.trip.trip_id,
                    route_id      = tu.trip.route_id,
                    delay_seconds = delay,
                    current_stop  = tu.stop_time_update[0].stop_id,
                    next_stop     = (tu.stop_time_update[1].stop_id
                                     if len(tu.stop_time_update) > 1 else "terminus"),
                )
    except Exception:
        return None
    return None

# ── Public API ─────────────────────────────────────────────────────────────────

def get_trip_update(
    route_id:  Optional[str] = None,
    feed_url:  Optional[str] = None,
) -> TripUpdate:
    """
    Return a TripUpdate for the given route.
    Tries live feed first; falls back to simulation.
    """
    if feed_url:
        live = _fetch_live(feed_url, route_id)
        if live:
            return live
    return _simulate_trip_update(route_id)
