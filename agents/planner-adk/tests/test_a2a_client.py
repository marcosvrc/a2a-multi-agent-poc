"""Unit tests for app/a2a/client.py's retry-with-backoff (Fase 8, §27):
transient transport failures (timeout, connection error, 5xx) get
retried up to `retry_attempts` extra times with exponential backoff; a
4xx status or a JSON-RPC-level error never gets retried.

httpx.AsyncClient itself is faked here (no `respx`/network dependency,
and no pytest-asyncio plugin in this venv — tests drive the coroutine
directly via `asyncio.run` instead of an `async def` + marker) — good
enough since what's under test is client.py's own retry/backoff control
flow, not httpx's transport behavior.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.a2a.client import A2AClient, A2AClientError


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://specialist/a2a")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(f"status {self.status_code}", request=request, response=response)

    def json(self) -> dict:
        return self._json


class _FakeAsyncClient:
    """Replaces httpx.AsyncClient for the duration of a test. `outcomes`
    is a shared list popped one item per attempt — either an exception to
    raise or a _FakeResponse to return.
    """

    def __init__(self, outcomes: list, calls: list, **_kwargs) -> None:
        self._outcomes = outcomes
        self._calls = calls

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def request(self, method: str, url: str, **kwargs) -> _FakeResponse:
        self._calls.append((method, url))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _patch_httpx(monkeypatch, outcomes: list) -> list:
    calls: list = []
    monkeypatch.setattr(
        "app.a2a.client.httpx.AsyncClient",
        lambda **kwargs: _FakeAsyncClient(outcomes, calls, **kwargs),
    )
    return calls


def test_succeeds_on_first_attempt_without_retry(monkeypatch):
    calls = _patch_httpx(monkeypatch, [_FakeResponse(200, {"jsonrpc": "2.0", "id": "1", "result": {"ok": True}})])
    client = A2AClient(retry_attempts=2, retry_backoff_base_seconds=0.01)

    result = asyncio.run(client.send_text("http://specialist", "hello"))

    assert result == {"ok": True}
    assert len(calls) == 1


def test_retries_on_transient_timeout_then_succeeds(monkeypatch):
    outcomes = [
        httpx.TimeoutException("timed out"),
        _FakeResponse(200, {"jsonrpc": "2.0", "id": "1", "result": {"ok": True}}),
    ]
    calls = _patch_httpx(monkeypatch, outcomes)
    client = A2AClient(retry_attempts=2, retry_backoff_base_seconds=0.01)

    result = asyncio.run(client.send_text("http://specialist", "hello"))

    assert result == {"ok": True}
    assert len(calls) == 2  # one failed attempt + one successful retry


def test_retries_on_5xx_then_succeeds(monkeypatch):
    outcomes = [
        _FakeResponse(503),
        _FakeResponse(200, {"jsonrpc": "2.0", "id": "1", "result": {"ok": True}}),
    ]
    calls = _patch_httpx(monkeypatch, outcomes)
    client = A2AClient(retry_attempts=2, retry_backoff_base_seconds=0.01)

    result = asyncio.run(client.send_text("http://specialist", "hello"))

    assert result == {"ok": True}
    assert len(calls) == 2


def test_does_not_retry_on_4xx(monkeypatch):
    calls = _patch_httpx(monkeypatch, [_FakeResponse(400)])
    client = A2AClient(retry_attempts=2, retry_backoff_base_seconds=0.01)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.send_text("http://specialist", "hello"))

    assert len(calls) == 1  # no retry on a client-side rejection


def test_does_not_retry_on_jsonrpc_level_error(monkeypatch):
    # A 200 response with a JSON-RPC "error" field means the specialist
    # DID process the request — retrying would violate §27's "não
    # repetir chamadas não idempotentes sem controle".
    calls = _patch_httpx(
        monkeypatch,
        [_FakeResponse(200, {"jsonrpc": "2.0", "id": "1", "error": {"code": -32000, "message": "bad input"}})],
    )
    client = A2AClient(retry_attempts=2, retry_backoff_base_seconds=0.01)

    with pytest.raises(A2AClientError):
        asyncio.run(client.send_text("http://specialist", "hello"))

    assert len(calls) == 1


def test_exhausts_retries_and_raises_last_exception(monkeypatch):
    outcomes = [httpx.ConnectError("refused"), httpx.ConnectError("refused"), httpx.ConnectError("refused")]
    calls = _patch_httpx(monkeypatch, outcomes)
    client = A2AClient(retry_attempts=2, retry_backoff_base_seconds=0.01)

    with pytest.raises(httpx.ConnectError):
        asyncio.run(client.send_text("http://specialist", "hello"))

    assert len(calls) == 3  # initial attempt + 2 retries, all exhausted


def test_zero_retry_attempts_means_single_try(monkeypatch):
    calls = _patch_httpx(monkeypatch, [httpx.TimeoutException("timed out")])
    client = A2AClient(retry_attempts=0, retry_backoff_base_seconds=0.01)

    with pytest.raises(httpx.TimeoutException):
        asyncio.run(client.send_text("http://specialist", "hello"))

    assert len(calls) == 1


def test_backoff_delay_grows_exponentially(monkeypatch):
    outcomes = [
        httpx.TimeoutException("1"),
        httpx.TimeoutException("2"),
        _FakeResponse(200, {"jsonrpc": "2.0", "id": "1", "result": {"ok": True}}),
    ]
    _patch_httpx(monkeypatch, outcomes)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    client = A2AClient(retry_attempts=2, retry_backoff_base_seconds=0.5)
    asyncio.run(client.send_text("http://specialist", "hello"))

    assert sleeps == [0.5, 1.0]  # 0.5 * 2**0, 0.5 * 2**1
