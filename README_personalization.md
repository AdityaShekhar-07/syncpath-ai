# SyncPath — Personalization Module

Privacy-first, rule-based user personalization for last-mile transit decisions.

---

## Folder Structure

```
syncpath-ai/
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── syncpath_users.db                # auto-created SQLite DB (local only)
├── personalization/
│   ├── __init__.py                  # DB init on import
│   ├── models.py                    # UserProfile schema + SQLite helpers
│   ├── preference_engine.py         # Rule-based scoring & ranking
│   ├── decision_engine.py           # Decision logic + explanation builder
│   ├── llm_integration.py           # Ollama (Llama 3) — optional NL refinement
│   ├── privacy_layer.py             # PII sanitizer for outgoing requests
│   ├── learning.py                  # Preference nudging from history (bonus)
│   └── api.py                       # FastAPI router
└── tests/
    └── test_personalization.py
```

---

## Setup & Run

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --reload
```

API docs available at: http://127.0.0.1:8000/docs

---

## Running Tests

```bash
pytest tests/ -v
```

---

## API Usage Examples

### Create a user
```bash
curl -X POST http://localhost:8000/personalization/create-user \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "commuter_01",
    "budget_preference": "low",
    "urgency_level": "high",
    "comfort_preference": "medium",
    "walking_tolerance": "low"
  }'
```

### Get a profile
```bash
curl http://localhost:8000/personalization/get-profile/commuter_01
```

### Update preferences
```bash
curl -X POST http://localhost:8000/personalization/update-preferences \
  -H "Content-Type: application/json" \
  -d '{"user_id": "commuter_01", "urgency_level": "medium"}'
```

### Get a decision
```bash
curl -X POST http://localhost:8000/personalization/get-decision \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "commuter_01",
    "situation": {
      "train_delay_minutes": 10,
      "surge_multiplier": 2.5,
      "ride_available": true,
      "weather_bad": false
    },
    "options": [
      {"name": "Metro+Auto",  "travel_time": 25, "cost": 60,  "comfort": 6, "walking_distance": 300},
      {"name": "Uber",        "travel_time": 18, "cost": 180, "comfort": 9, "walking_distance": 50},
      {"name": "Bus",         "travel_time": 40, "cost": 20,  "comfort": 4, "walking_distance": 500},
      {"name": "Walk",        "travel_time": 55, "cost": 0,   "comfort": 3, "walking_distance": 4000}
    ],
    "use_llm": false
  }'
```

Set `"use_llm": true` to refine the explanation via Ollama (requires `ollama serve` with `llama3` pulled).

---

## Privacy Guarantee

- All user data is stored in a local SQLite file (`syncpath_users.db`).
- `privacy_layer.sanitize_payload()` must be called before any external API request.
- `user_id`, `name`, `phone`, `email`, `address` are replaced with one-way hash tokens.
- Inline email/phone patterns in string values are scrubbed automatically.

---

## Decision Logic (No LLM Required)

```
score = w_time*(1−norm_time) + w_cost*(1−norm_cost)
      + w_comfort*norm_comfort + w_walk*(1−norm_walk)
```

Weights are derived from user preferences:
| Preference        | Effect                          |
|-------------------|---------------------------------|
| high urgency      | w_time × 2.0                    |
| low budget        | w_cost × 2.0                    |
| high comfort      | w_comfort × 2.0                 |
| low walking tol.  | w_walk × 2.0                    |

Live situation adjustments applied before scoring:
- Surge multiplier applied to ride-hailing costs
- Train delay added to transit travel times
- Unavailable options pushed to bottom of ranking
