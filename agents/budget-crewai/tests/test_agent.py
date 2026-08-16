import json
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app import agent as agent_module
from app import mcp_client as agent_mcp_client
from app.config import settings
from app.main import app

# Fase 9 (§7/§56): the /a2a route now requires a bearer token by
# default (AUTH_MODE=dev) — every test in this file authenticates as
# whatever holds the shared DEV_AGENT_TOKEN, same as any real caller
# would in the default deployment.
client = TestClient(app, headers={"Authorization": f"Bearer {settings.dev_agent_token}"})

MOCK_FLIGHT = {
    "status": "SUCCESS",
    "options": [{"id": "FL-0001", "price": 1000.0, "currency": "BRL"}],
    "recommended_option_id": "FL-0001",
}
MOCK_HOTEL = {
    "status": "SUCCESS",
    "options": [{"id": "HT-0001", "price_per_night": 300.0, "currency": "BRL"}],
}
MOCK_ACTIVITIES = {
    "status": "SUCCESS",
    "days": [
        {"date": "2026-09-20", "weather": None, "items": [{"name": "Praia", "start_time": "09:00", "category": "beach"}]},
        {"date": "2026-09-21", "weather": None, "items": [{"name": "Museu", "start_time": "09:00", "category": "museum"}]},
    ],
}


def test_health():
    assert client.get("/health").json() == {"status": "UP"}


def test_agent_card_has_calculate_budget_skill():
    card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "budget-agent"
    assert any(s["id"] == "calculate_budget" for s in card["skills"])


def _send(payload: dict, context_id: str) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps(payload)}],
                "context_id": context_id,
            }
        },
    }
    resp = client.post("/a2a", json=body)
    task = resp.json()["result"]
    return json.loads(task["status"]["message"]["parts"][0]["text"])


def _mock_calculator_and_currency(monkeypatch):
    monkeypatch.setattr(agent_module, "calc_sum", AsyncMock(side_effect=lambda url, a, b, t=30.0: a + b))
    monkeypatch.setattr(agent_module, "calc_subtract", AsyncMock(side_effect=lambda url, a, b, t=30.0: a - b))
    monkeypatch.setattr(agent_module, "calc_multiply", AsyncMock(side_effect=lambda url, a, b, t=30.0: a * b))
    monkeypatch.setattr(agent_module, "convert_currency", AsyncMock(side_effect=lambda url, *, amount, from_currency, to_currency, timeout_seconds=30.0: amount))


# Same fixed illustrative exchange-rate table mcp/currency/app/mock_data.py
# uses (rates relative to BRL) — duplicated here (rather than imported,
# since mcp/currency is a separate, independently-deployed service with
# its own venv/requirements) so the real-transport tests below exercise
# genuine (non-identity) conversion math, not just an amount-passthrough.
_RATES_PER_BRL = {"BRL": 1.0, "USD": 0.18, "EUR": 0.17}


def _real_call_mcp_tool(mcp_url, tool_name, arguments, timeout_seconds=30.0):
    """Stands in for app.mcp_client.call_mcp_tool, replicating exactly what
    mcp/calculator and mcp/currency's real tool handlers compute (see
    mcp/calculator/app/server.py and mcp/currency/app/mock_data.py) — so
    tests using this exercise the real calc_sum/calc_subtract/
    calc_multiply/convert_currency parsing-and-arithmetic logic in
    app/mcp_client.py end to end, instead of mocking those wrappers away
    entirely (which would never catch a real arithmetic or
    response-shape bug).
    """
    if tool_name == "sum":
        return {"result": arguments["a"] + arguments["b"]}
    if tool_name == "subtract":
        return {"result": arguments["a"] - arguments["b"]}
    if tool_name == "multiply":
        return {"result": arguments["a"] * arguments["b"]}
    if tool_name == "convert_currency":
        from_rate = _RATES_PER_BRL.get(arguments["from_currency"].upper())
        to_rate = _RATES_PER_BRL.get(arguments["to_currency"].upper())
        if from_rate is None or to_rate is None:
            return {"provider": "mock", "conversion": None}
        amount_in_brl = arguments["amount"] / from_rate
        converted = amount_in_brl * to_rate
        return {"provider": "mock", "conversion": {"converted_amount": round(converted, 2)}}
    raise AssertionError(f"unexpected tool call: {tool_name}")


def _mock_real_arithmetic(monkeypatch):
    """Patches only the MCP transport boundary (call_mcp_tool) — unlike
    _mock_calculator_and_currency above, calc_sum/calc_subtract/
    calc_multiply/convert_currency in app/mcp_client.py run for real
    against the stub above.
    """
    monkeypatch.setattr(agent_module, "calc_sum", agent_mcp_client.calc_sum)
    monkeypatch.setattr(agent_module, "calc_subtract", agent_mcp_client.calc_subtract)
    monkeypatch.setattr(agent_module, "calc_multiply", agent_mcp_client.calc_multiply)
    monkeypatch.setattr(agent_module, "convert_currency", agent_mcp_client.convert_currency)
    monkeypatch.setattr(agent_mcp_client, "call_mcp_tool", AsyncMock(side_effect=_real_call_mcp_tool))


def test_within_budget(monkeypatch):
    _mock_calculator_and_currency(monkeypatch)
    result = _send(
        {
            "budget_limit": 100000,
            "currency": "BRL",
            "travelers": 2,
            "nights": 2,
            "flight": MOCK_FLIGHT,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-1",
    )
    assert result["status"] == "SUCCESS"
    assert result["budget_status"] == "WITHIN_BUDGET"
    assert result["flight_cost"] == 1000.0
    assert result["hotel_cost"] == 600.0  # 300 * 2 nights
    assert result["activity_cost"] == 160.0  # (beach(20) + museum(60)) * 2 travelers
    assert result["total"] > 0
    assert result["remaining"] == round(100000 - result["total"], 2)


def test_over_budget(monkeypatch):
    _mock_calculator_and_currency(monkeypatch)
    result = _send(
        {
            "budget_limit": 100,
            "currency": "BRL",
            "travelers": 2,
            "nights": 2,
            "flight": MOCK_FLIGHT,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-2",
    )
    assert result["budget_status"] == "OVER_BUDGET"


def test_missing_budget_limit_returns_unknown(monkeypatch):
    _mock_calculator_and_currency(monkeypatch)
    result = _send(
        {
            "currency": "BRL",
            "travelers": 1,
            "nights": 1,
            "flight": MOCK_FLIGHT,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-3",
    )
    assert result["status"] == "UNKNOWN"
    assert result["budget_status"] == "UNKNOWN"


def test_missing_flight_treated_as_zero_cost_and_noted(monkeypatch):
    _mock_calculator_and_currency(monkeypatch)
    result = _send(
        {
            "budget_limit": 10000,
            "currency": "BRL",
            "travelers": 1,
            "nights": 1,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-4",
    )
    assert result["status"] == "PARTIAL"
    assert result["flight_cost"] == 0
    assert "flight" in result["notes"]


def test_calculator_unavailable_returns_unavailable_status(monkeypatch):
    async def raise_error(*args, **kwargs):
        raise agent_module.McpToolError("connection refused")

    monkeypatch.setattr(agent_module, "calc_sum", raise_error)

    result = _send(
        {
            "budget_limit": 10000,
            "currency": "BRL",
            "travelers": 1,
            "nights": 1,
            "flight": MOCK_FLIGHT,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-5",
    )
    assert result["status"] == "UNAVAILABLE"


def test_invalid_json_fails_task():
    body = {
        "jsonrpc": "2.0",
        "id": "6",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "not json"}],
                "context_id": "ctx-budget-6",
            }
        },
    }
    resp = client.post("/a2a", json=body)
    task = resp.json()["result"]
    assert task["status"]["state"] == "failed"


def test_real_arithmetic_within_budget(monkeypatch):
    # Same scenario as test_within_budget, but exercising the real
    # calc_sum/calc_multiply/convert_currency parsing-and-arithmetic code
    # path (app/mcp_client.py) instead of mocking those functions out —
    # catches bugs those other tests structurally cannot (e.g. a broken
    # `raw["result"]`/`raw.get("conversion")` extraction, or the actual
    # BRL total math being wrong).
    _mock_real_arithmetic(monkeypatch)
    result = _send(
        {
            "budget_limit": 100000,
            "currency": "BRL",
            "travelers": 2,
            "nights": 2,
            "flight": MOCK_FLIGHT,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-7",
    )
    assert result["status"] == "SUCCESS"
    assert result["flight_cost"] == 1000.0
    assert result["hotel_cost"] == 600.0
    assert result["activity_cost"] == 160.0
    # food/transport: settings defaults are 120/60 BRL per traveler per
    # night * 2 travelers * 2 nights.
    assert result["food_estimate"] == 480.0
    assert result["transport_estimate"] == 240.0
    assert result["total"] == 1000.0 + 600.0 + 160.0 + 480.0 + 240.0
    assert result["budget_status"] == "WITHIN_BUDGET"


def test_real_currency_conversion_non_identity(monkeypatch):
    # Requests a currency other than BRL (the mock data's base currency)
    # so this only passes if convert_currency's real, non-identity
    # conversion math actually ran — the identity `amount` passthrough
    # in _mock_calculator_and_currency would make a bug here invisible.
    _mock_real_arithmetic(monkeypatch)
    result = _send(
        {
            "budget_limit": 100000,
            "currency": "USD",
            "travelers": 1,
            "nights": 1,
            "flight": MOCK_FLIGHT,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-8",
    )
    assert result["status"] == "SUCCESS"
    # flight_cost 1000 BRL -> USD at rate 0.18 = 180.0
    assert result["flight_cost"] == 180.0


def test_near_limit_status(monkeypatch):
    _mock_calculator_and_currency(monkeypatch)
    # total will be flight(1000) + hotel(300*1) + activities(80) +
    # food(120) + transport(60) = 1560; a limit of 1800 puts the ratio at
    # 1560/1800 ≈ 0.867, inside the (0.8, 1.0] NEAR_LIMIT band.
    result = _send(
        {
            "budget_limit": 1800,
            "currency": "BRL",
            "travelers": 1,
            "nights": 1,
            "flight": MOCK_FLIGHT,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-9",
    )
    assert result["budget_status"] == "NEAR_LIMIT"


def test_budget_status_boundary_exactly_at_80_percent():
    assert agent_module._budget_status(80.0, 100.0) == "WITHIN_BUDGET"


def test_budget_status_boundary_exactly_at_100_percent():
    assert agent_module._budget_status(100.0, 100.0) == "NEAR_LIMIT"


def test_budget_status_just_over_100_percent():
    assert agent_module._budget_status(100.01, 100.0) == "OVER_BUDGET"


def test_budget_status_zero_limit_with_spend_is_over_budget():
    assert agent_module._budget_status(1.0, 0.0) == "OVER_BUDGET"


def test_budget_status_zero_limit_with_no_spend_is_within_budget():
    assert agent_module._budget_status(0.0, 0.0) == "WITHIN_BUDGET"


def test_malformed_request_fields_degrade_instead_of_crashing(monkeypatch):
    _mock_calculator_and_currency(monkeypatch)
    result = _send(
        {
            "budget_limit": "not-a-number",
            "currency": "BRL",
            "travelers": 1,
            "nights": 1,
            "flight": MOCK_FLIGHT,
            "hotel": MOCK_HOTEL,
            "activities": MOCK_ACTIVITIES,
        },
        "ctx-budget-10",
    )
    assert result["status"] == "UNAVAILABLE"
    assert result["budget_status"] == "UNKNOWN"
