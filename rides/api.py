"""
rides/api.py — FastAPI router for ride-hailing availability queries.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from .simulator import get_ride_options, get_best_ride, RideOption

router = APIRouter(prefix="/rides", tags=["Rides"])

class RideOptionResponse(BaseModel):
    ride_type:        str
    available:        bool
    surge_multiplier: float
    base_fare:        float
    total_fare:       float
    eta_minutes:      float
    drivers_nearby:   int

class RideQueryRequest(BaseModel):
    distance_km:   float = 5.0
    duration_min:  float = 20.0
    demand_factor: float = 1.0

def _to_response(o: RideOption) -> RideOptionResponse:
    return RideOptionResponse(
        ride_type        = o.ride_type.value,
        available        = o.available,
        surge_multiplier = o.surge_multiplier,
        base_fare        = o.base_fare,
        total_fare       = o.total_fare,
        eta_minutes      = o.eta_minutes,
        drivers_nearby   = o.drivers_nearby,
    )

@router.post("/options", response_model=list[RideOptionResponse])
def ride_options(req: RideQueryRequest):
    """Get all ride options with live surge and availability."""
    return [_to_response(o) for o in get_ride_options(
        req.distance_km, req.duration_min, req.demand_factor
    )]

@router.post("/best", response_model=RideOptionResponse | None)
def best_ride(req: RideQueryRequest, prefer_cheap: bool = False):
    """Get the single best available ride."""
    ride = get_best_ride(req.distance_km, req.duration_min, req.demand_factor, prefer_cheap)
    return _to_response(ride) if ride else None
