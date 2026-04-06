"""
agents/api.py — FastAPI router to trigger a SyncPath crew run.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/agents", tags=["Agents"])

class CrewRunRequest(BaseModel):
    route_id:      str
    distance_km:   float = 5.0
    demand_factor: float = 1.0
    user_id:       str | None = None

@router.post("/run")
def run_crew_endpoint(req: CrewRunRequest):
    """
    Trigger a full SyncPath crew run.
    Requires crewai + ollama running locally.
    Returns agent recommendation + optional personalized decision.
    """
    try:
        from agents.crew import run_crew
        result = run_crew(
            route_id      = req.route_id,
            distance_km   = req.distance_km,
            demand_factor = req.demand_factor,
            user_id       = req.user_id,
        )
        return result
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="crewai not installed. Run: pip install crewai"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
