"""Deterministic mock weather data (PROJECT_SPEC.md §23: mocks must be
deterministic — same input always yields the same output, no randomness).
"MCP Weather poderá usar mock local" (§5.4).
"""
from __future__ import annotations

import hashlib

_CONDITIONS = ["Ensolarado", "Parcialmente nublado", "Nublado", "Chuva leve", "Chuva forte"]
_BASE_TEMPERATURE_C = 18.0


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def get_weather_mock(destination: str, date: str) -> dict:
    seed = _stable_seed(destination, date)
    condition = _CONDITIONS[seed % len(_CONDITIONS)]
    temperature_c = round(_BASE_TEMPERATURE_C + (seed % 150) / 10, 1)
    return {
        "date": date,
        "condition": condition,
        "temperature_c": temperature_c,
    }
