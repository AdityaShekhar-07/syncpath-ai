"""
llm_integration.py — Thin wrapper around Ollama (Llama 3) for natural-language
explanation refinement ONLY. Rule-based logic is never replaced by the LLM.

Ollama must be running locally: `ollama serve` with `llama3` pulled.
"""

import httpx

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
TIMEOUT      = 15  # seconds — fail fast so the API stays responsive

_SYSTEM_PROMPT = (
    "You are a concise transit assistant. "
    "Rewrite the following decision explanation in one friendly sentence "
    "without adding new facts or changing the recommendation."
)

def refine_explanation(raw_explanation: str) -> str:
    """
    Send the rule-based explanation to Ollama for a friendlier rewrite.
    Returns the original string if Ollama is unavailable or times out.
    """
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": f"{_SYSTEM_PROMPT}\n\nExplanation: {raw_explanation}",
        "stream": False,
    }
    try:
        resp = httpx.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("response", raw_explanation).strip()
    except Exception:
        # Ollama unavailable → silently return original
        return raw_explanation
