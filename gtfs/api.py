"""
gtfs/api.py — FastAPI router for GTFS trip update queries.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from .feed import get_trip_update, TripUpdate

router = APIRouter(prefix="/gtfs", tags=["GTFS"])

class TripUpdateResponse(BaseModel):
    trip_id:       str
    route_id:      str
    delay_seconds: int
    delay_minutes: float
    current_stop:  str
    next_stop:     str
    timestamp:     float

@router.get("/trip-update", response_model=TripUpdateResponse)
def trip_update(route_id: str | None = None, feed_url: str | None = None):
    """
    Get the latest trip update for a route.
    Uses live GTFS-RT feed if feed_url is provided, otherwise simulates.
    """
    update = get_trip_update(route_id=route_id, feed_url=feed_url)
    return TripUpdateResponse(
        trip_id       = update.trip_id,
        route_id      = update.route_id,
        delay_seconds = update.delay_seconds,
        delay_minutes = update.delay_minutes,
        current_stop  = update.current_stop,
        next_stop     = update.next_stop,
        timestamp     = update.timestamp,
    )
