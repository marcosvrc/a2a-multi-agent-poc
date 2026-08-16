"""Deterministic mock exchange rates (PROJECT_SPEC.md §23: mocks must be
deterministic — same input always yields the same output, no randomness).
Illustrative fixed snapshot, not a real-time rate feed (no real currency
API was specified, and §31 forbids inventing data that pretends to be
real). Rates are expressed relative to BRL.
"""
from __future__ import annotations

_RATES_PER_BRL = {
    "BRL": 1.0,
    "USD": 0.18,
    "EUR": 0.17,
    "GBP": 0.145,
    "ARS": 165.0,
    "CLP": 175.0,
}


def convert_currency_mock(amount: float, from_currency: str, to_currency: str) -> dict | None:
    from_rate = _RATES_PER_BRL.get(from_currency.upper())
    to_rate = _RATES_PER_BRL.get(to_currency.upper())
    if from_rate is None or to_rate is None:
        return None

    # amount (in from_currency) -> BRL -> to_currency
    amount_in_brl = amount / from_rate
    converted = amount_in_brl * to_rate
    rate = to_rate / from_rate

    return {
        "amount": amount,
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "converted_amount": round(converted, 2),
        "rate": round(rate, 6),
    }
