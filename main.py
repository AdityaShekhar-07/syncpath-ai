"""
main.py — SyncPath unified FastAPI application.

Routers:
  /personalization  — user profiles, preferences, decisions
  /gtfs             — live transit delay data
  /rides            — ride-hailing availability & surge
  /agents           — CrewAI crew trigger (requires crewai + ollama)

Run: uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from personalization.api import router as personalization_router
from gtfs.api             import router as gtfs_router
from rides.api            import router as rides_router
from agents.api           import router as agents_router

app = FastAPI(
    title       = "SyncPath AI — Transit Orchestrator",
    description = "Privacy-first, multi-agent last-mile transit orchestration.",
    version     = "2.0.0",
)

# Allow Streamlit UI (localhost:8501) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(personalization_router)
app.include_router(gtfs_router)
app.include_router(rides_router)
app.include_router(agents_router)

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "syncpath-ai", "version": "2.0.0"}
