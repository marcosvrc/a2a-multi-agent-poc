"""Deterministic mock flight data (PROJECT_SPEC.md §23: mocks must be
deterministic — same input always yields the same output, no randomness).
"""
from __future__ import annotations

import hashlib

_CARRIERS = ["LATAM", "GOL", "Azul", "TAP", "Avianca"]
_BASE_PRICE = 420.0


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def search_flights_mock(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int,
) -> list[dict]:
    seed = _stable_seed(origin, destination, start_date, end_date, str(travelers))
    flights: list[dict] = []
    for i in range(5):
        carrier = _CARRIERS[(seed + i) % len(_CARRIERS)]
        price = round(_BASE_PRICE + ((seed >> (i * 4)) % 400) + (i * 35), 2)
        flights.append(
            {
                "id": f"FL-{(seed + i) % 10000:04d}",
                "origin": origin,
                "destination": destination,
                "price": price * max(travelers, 1),
                "currency": "BRL",
                "provider": "mock",
                "carrier": carrier,
                "departure_date": start_date,
                "return_date": end_date,
            }
        )
    return flights
