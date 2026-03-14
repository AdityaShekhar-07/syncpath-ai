# SyncPath: Autonomous Last-Mile Transit Orchestrator 🚀

**SyncPath** is an open-source, multi-agent AI framework designed to solve the "fragmented journey" problem. By synchronizing real-time public transit delays (Metro/Trains) with last-mile service providers (Uber/Auto), SyncPath ensures your commute remains seamless even when transit schedules fail.

---

## 📌 Overview

Commuters often face "last-mile anxiety"—where a 5-minute delay in a Metro train leads to a canceled cab or a long wait in a high-demand zone. 

SyncPath transitions from **static navigation** to **agentic orchestration**. It doesn't just show you the route; it actively monitors your journey and takes autonomous corrective actions (like rescheduling a ride or suggesting a bike-taxi) to keep you on schedule.

## 🤖 The Agentic Workforce

Built using **CrewAI**, the system employs a specialized "crew" of agents:

* **The Transit Watcher:** Polls live GTFS (General Transit Feed Specification) data to track your specific train/metro vehicle.
* **The Logistics Agent:** Monitors ride-sharing availability, surge pricing, and traffic conditions at your destination station.
* **The Orchestrator:** The brain of the operation. It receives delay alerts from the Watcher and coordinates with the Logistics agent to reschedule pickups or suggest modal shifts.

## 🛠️ Tech Stack

- **Orchestration:** [CrewAI](https://www.crewai.com/) / [LangGraph](https://www.langchain.com/langgraph)
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **LLM Support:** OpenAI GPT-4o-mini (Reasoning) & [Ollama](https://ollama.com/) (for privacy-first local processing)
- **Data Layer:** Real-time GTFS Feeds & Simulated Ride-hailing APIs

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- OpenAI API Key or Ollama installed locally

### Installation
1. **Clone the Repo:**
   ```bash
   git clone [https://github.com/AdityaShekhar-07/syncpath-ai.git](https://github.com/AdityaShekhar-07/syncpath-ai.git)
   cd syncpath-ai
