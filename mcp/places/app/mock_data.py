"""Deterministic mock places data (PROJECT_SPEC.md §23: mocks must be
deterministic — same input always yields the same output, no randomness).
"""
from __future__ import annotations

import hashlib

_CATEGORIES = [
    "sightseeing",
    "museum",
    "beach",
    "hiking",
    "food",
    "shopping",
    "nightlife",
    "culture",
]

_NAME_TEMPLATES = {
    "sightseeing": ["Mirante {d}", "Centro Histórico de {d}", "Passeio Panorâmico {d}"],
    "museum": ["Museu de Arte de {d}", "Museu Histórico de {d}"],
    "beach": ["Praia Central de {d}", "Praia do Farol ({d})"],
    "hiking": ["Trilha da Serra ({d})", "Trilha do Mirante ({d})"],
    "food": ["Mercado Municipal de {d}", "Feira Gastronômica de {d}"],
    "shopping": ["Rua do Comércio de {d}", "Mercado de Artesanato de {d}"],
    "nightlife": ["Bairro Boêmio de {d}", "Orla Noturna de {d}"],
    "culture": ["Teatro Municipal de {d}", "Centro Cultural de {d}"],
}

_DURATIONS = {
    "sightseeing": 90,
    "museum": 120,
    "beach": 180,
    "hiking": 150,
    "food": 90,
    "shopping": 90,
    "nightlife": 120,
    "culture": 100,
}


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def search_places_mock(destination: str, preferences: list[str] | None = None, limit: int = 10) -> list[dict]:
    """Returns up to `limit` mock places for `destination`. When
    `preferences` matches known categories, those categories are
    prioritized first — but never exclusively, so there is always enough
    variety to fill an itinerary (§5.4: "considerar preferências").
    """
    preferences = preferences or []
    matched = [c for c in _CATEGORIES if c in preferences]
    rest = [c for c in _CATEGORIES if c not in matched]
    ordered_categories = matched + rest

    places: list[dict] = []
    for category in ordered_categories:
        seed = _stable_seed(destination, category)
        templates = _NAME_TEMPLATES[category]
        name = templates[seed % len(templates)].format(d=destination)
        places.append(
            {
                "id": f"PL-{seed % 10000:04d}",
                "name": name,
                "category": category,
                "duration_minutes": _DURATIONS[category],
            }
        )
        if len(places) >= limit:
            break
    return places[:limit]
