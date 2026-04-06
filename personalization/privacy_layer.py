"""
privacy_layer.py — Ensures user PII never leaves the local system.

Rules:
  - Strip user_id, name, phone, email from any outgoing payload.
  - Replace with anonymous tokens.
  - All user data is stored locally (SQLite); only anonymised queries go out.
"""

import hashlib
import re
from typing import Any

# Fields considered PII — extend as needed
_PII_FIELDS = {"user_id", "name", "phone", "email", "address", "device_id"}

# Regex patterns for inline PII in string values
_PII_PATTERNS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.I), "<email>"),
    (re.compile(r"\b\d{10}\b"),                            "<phone>"),
    (re.compile(r"\b\d{12}\b"),                            "<aadhaar>"),
]

def _anonymise_value(value: str) -> str:
    """Scrub inline PII patterns from a string value."""
    for pattern, placeholder in _PII_PATTERNS:
        value = pattern.sub(placeholder, value)
    return value

def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively remove PII fields and scrub PII patterns from string values.
    Returns a new dict; original is not mutated.
    """
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in _PII_FIELDS:
            # Replace with a one-way hash token so the request stays linkable
            # within a session without exposing the real identifier.
            clean[key] = "anon_" + hashlib.sha256(str(value).encode()).hexdigest()[:8]
        elif isinstance(value, dict):
            clean[key] = sanitize_payload(value)
        elif isinstance(value, list):
            clean[key] = [
                sanitize_payload(v) if isinstance(v, dict)
                else (_anonymise_value(v) if isinstance(v, str) else v)
                for v in value
            ]
        elif isinstance(value, str):
            clean[key] = _anonymise_value(value)
        else:
            clean[key] = value
    return clean

def safe_external_query(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Entry point for any data leaving the local system.
    Always call this before sending to an external API.
    """
    return sanitize_payload(payload)
