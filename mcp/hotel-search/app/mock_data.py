"""Deterministic mock hotel data (PROJECT_SPEC.md §23: same input -> same
output, no randomness).
"""
from __future__ import annotations

import hashlib

_HOTEL_NAMES = [
    "Pousada Mar Azul",
    "Hotel Central Plaza",
    "Resort Costa Verde",
    "Ilha Bela Suites",
    "Vila das Palmeiras",
    "Grand Hotel Continental",
]
_LOCATIONS = ["Centro", "Praia", "Zona Turistica", "Orla", "Bairro Historico"]
_BASE_PRICE = 180.0


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def search_hotels_mock(
    destination: str,
    start_date: str,
    end_date: str,
    guests: int,
) -> list[dict]:
    seed = _stable_seed(destination, start_date, end_date, str(guests))
    hotels: list[dict] = []
    for i in range(6):
        name = _HOTEL_NAMES[(seed + i) % len(_HOTEL_NAMES)]
        location = _LOCATIONS[(seed + i * 3) % len(_LOCATIONS)]
        price = round(_BASE_PRICE + ((seed >> (i * 3)) % 250) + (i * 22), 2)
        rating = round(3.0 + ((seed + i * 7) % 20) / 10, 1)
        hotels.append(
            {
                "id": f"HT-{(seed + i) % 10000:04d}",
                "name": name,
                "price_per_night": price,
                "currency": "BRL",
                "rating": min(rating, 5.0),
                "location": location,
                "destination": destination,
            }
        )
    return hotels
