"""
agents/crew.py — SyncPath CrewAI crew.

Agents:
  1. Transit Watcher   — monitors GTFS delays for a given route
  2. Logistics Agent   — checks ride availability and surge at destination
  3. Orchestrator      — synthesises both inputs + user profile → final recommendation

The crew runs sequentially; the Orchestrator receives context from both
upstream agents and calls the personalization decision engine directly.
"""

import json
from crewai import Agent, Task, Crew, Process
from crewai.llm import LLM

from .tools import get_transit_delay, get_ride_availability, get_best_ride_option
from personalization.models import load_user
from personalization.preference_engine import TransportOption
from personalization.decision_engine import SituationContext, make_decision

# ── LLM config (Ollama Llama3 — local, privacy-first) ─────────────────────────

_llm = LLM(model="ollama/llama3", base_url="http://localhost:11434")

# ── Agent definitions ──────────────────────────────────────────────────────────

transit_watcher = Agent(
    role="Transit Watcher",
    goal="Monitor real-time GTFS data and report accurate delay information for the user's route.",
    backstory=(
        "You are a specialist in public transit data. You poll live GTFS feeds "
        "and translate raw delay data into actionable alerts for the orchestrator."
    ),
    tools=[get_transit_delay],
    llm=_llm,
    verbose=True,
)

logistics_agent = Agent(
    role="Logistics Agent",
    goal="Monitor ride-hailing availability, surge pricing, and ETAs at the destination station.",
    backstory=(
        "You are an expert in last-mile mobility. You track ride-sharing supply, "
        "demand surges, and traffic conditions to give the orchestrator accurate "
        "cost and availability data."
    ),
    tools=[get_ride_availability, get_best_ride_option],
    llm=_llm,
    verbose=True,
)

orchestrator = Agent(
    role="Orchestrator",
    goal=(
        "Synthesise transit delay data and ride availability to recommend the best "
        "commute option for the user, respecting their personal preferences."
    ),
    backstory=(
        "You are the brain of SyncPath. You receive delay alerts and logistics data, "
        "then coordinate a personalised recommendation that keeps the commuter on schedule."
    ),
    tools=[],   # Orchestrator reasons; tools are called by upstream agents
    llm=_llm,
    verbose=True,
)

# ── Task factory ───────────────────────────────────────────────────────────────

def build_tasks(route_id: str, distance_km: float, demand_factor: float) -> list[Task]:
    watch_task = Task(
        description=(
            f"Check the current delay for metro route '{route_id}'. "
            "Report delay_minutes, current_stop, and next_stop."
        ),
        expected_output="JSON with delay_minutes, current_stop, next_stop.",
        agent=transit_watcher,
    )

    logistics_task = Task(
        description=(
            f"Check ride availability for a {distance_km} km trip "
            f"with demand_factor={demand_factor}. "
            "Report available rides, surge multipliers, fares, and ETAs."
        ),
        expected_output="JSON list of available ride options.",
        agent=logistics_agent,
    )

    orchestrate_task = Task(
        description=(
            "Using the transit delay report and ride availability data, "
            "determine the best commute option. Consider that the user may have "
            "specific budget, urgency, and comfort preferences. "
            "Provide a clear recommendation with a one-paragraph explanation."
        ),
        expected_output="A recommendation string with the best option and reasoning.",
        agent=orchestrator,
        context=[watch_task, logistics_task],
    )

    return [watch_task, logistics_task, orchestrate_task]

# ── Public API ─────────────────────────────────────────────────────────────────

def run_crew(
    route_id:      str,
    distance_km:   float,
    demand_factor: float = 1.0,
    user_id:       str | None = None,
) -> dict:
    """
    Run the full SyncPath crew for a journey.
    If user_id is provided, the personalization engine overrides the
    Orchestrator's raw output with a scored, preference-aware decision.
    """
    tasks = build_tasks(route_id, distance_km, demand_factor)
    crew  = Crew(
        agents  = [transit_watcher, logistics_agent, orchestrator],
        tasks   = tasks,
        process = Process.sequential,
        verbose = True,
    )

    crew_result = crew.kickoff()
    agent_recommendation = str(crew_result)

    # ── Personalization override ───────────────────────────────────────────────
    if user_id:
        profile = load_user(user_id)
        if profile:
            # Parse delay from watch_task output (best-effort)
            try:
                delay_data = json.loads(tasks[0].output.raw)
                delay_min  = float(delay_data.get("delay_minutes", 0))
            except Exception:
                delay_min = 0.0

            # Parse surge from logistics_task output (best-effort)
            try:
                ride_data = json.loads(tasks[1].output.raw)
                surges    = [r["surge_multiplier"] for r in ride_data if r.get("available")]
                surge     = min(surges) if surges else 1.0
                ride_avail = any(r.get("available") for r in ride_data)
            except Exception:
                surge, ride_avail = 1.0, True

            # Build standard transport options from ride data
            options = [
                TransportOption("Metro+Auto",  travel_time=25 + delay_min, cost=60,  comfort=6, walking_distance=300),
                TransportOption("Uber Go",     travel_time=distance_km * 3, cost=50 + distance_km * 12 * surge, comfort=9, walking_distance=50, available=ride_avail),
                TransportOption("Uber Auto",   travel_time=distance_km * 3.5, cost=30 + distance_km * 8 * surge, comfort=7, walking_distance=50, available=ride_avail),
                TransportOption("Rapido Bike", travel_time=distance_km * 2.5, cost=20 + distance_km * 5 * surge, comfort=4, walking_distance=50, available=ride_avail),
                TransportOption("Bus",         travel_time=40, cost=20, comfort=3, walking_distance=500),
            ]

            ctx    = SituationContext(train_delay_minutes=delay_min, surge_multiplier=surge, ride_available=ride_avail)
            result = make_decision(profile, ctx, options)

            return {
                "personalized_recommendation": result.best_option.name,
                "explanation":                 result.explanation,
                "score":                       result.score,
                "ranked":                      [{"rank": s.rank, "name": s.option.name, "score": s.score} for s in result.ranked_list],
                "agent_recommendation":        agent_recommendation,
            }

    return {"agent_recommendation": agent_recommendation}
