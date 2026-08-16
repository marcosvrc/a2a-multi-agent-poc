from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

# Fase 9 (§7/§56): the /a2a route now requires a bearer token by
# default (AUTH_MODE=dev) — every test in this file authenticates as
# whatever holds the shared DEV_AGENT_TOKEN, same as any real caller
# would in the default deployment.
client = TestClient(app, headers={"Authorization": f"Bearer {settings.dev_agent_token}"})


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "UP"}


def test_ready():
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "READY"


def test_agent_card():
    resp = client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
    card = resp.json()
    assert card["name"] == "mock-specialist-agent"
    skill_ids = [s["id"] for s in card["skills"]]
    assert "echo_ping" in skill_ids


def test_message_send_echoes_text():
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "hello a2a"}],
                "context_id": "ctx-test",
            }
        },
    }
    resp = client.post("/a2a", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "error" not in body or body["error"] is None
    task = body["result"]
    assert task["status"]["state"] == "completed"
    reply_text = task["status"]["message"]["parts"][0]["text"]
    assert "hello a2a" in reply_text


def test_message_send_missing_message_returns_jsonrpc_error():
    payload = {"jsonrpc": "2.0", "id": "2", "method": "message/send", "params": {}}
    resp = client.post("/a2a", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32602


def test_unknown_method_returns_method_not_found():
    payload = {"jsonrpc": "2.0", "id": "3", "method": "message/stream", "params": {}}
    resp = client.post("/a2a", json=payload)
    body = resp.json()
    assert body["error"]["code"] == -32601


def test_non_dict_json_body_returns_jsonrpc_error_not_500():
    # A body that's valid JSON but not a JSON-RPC object (e.g. a bare
    # array) used to reach `body.get("id")` and raise an unhandled
    # AttributeError -> 500, instead of a proper JSON-RPC error envelope.
    # This regression covers all 5 identical app/a2a/server.py copies
    # (planner-adk, flight-openai, activity-beeai, budget-crewai,
    # mock-specialist).
    resp = client.post("/a2a", json=[1, 2, 3])
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32600


def test_tasks_get_roundtrip():
    send_payload = {
        "jsonrpc": "2.0",
        "id": "4",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "track me"}],
                "context_id": "ctx-track",
            }
        },
    }
    task = client.post("/a2a", json=send_payload).json()["result"]
    task_id = task["id"]

    get_payload = {"jsonrpc": "2.0", "id": "5", "method": "tasks/get", "params": {"id": task_id}}
    resp = client.post("/a2a", json=get_payload)
    body = resp.json()
    assert body["result"]["id"] == task_id
