"""Unit tests for app/mcp_client.py's retry-with-backoff (Fase 8, §27).
The exact same `call_mcp_tool`/`_with_retry` pattern is duplicated in
flight-openai, budget-crewai and aws-strands — this is the one place it's
unit-tested directly (mirrors how test_a2a_client.py in planner-adk is
the one place A2AClient's retry gets a dedicated test).
"""
from __future__ import annotations

import asyncio

import pytest

from app.mcp_client import McpToolError, _with_retry, call_mcp_tool


def test_with_retry_succeeds_on_first_attempt():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = asyncio.run(_with_retry(fn, retry_attempts=2, retry_backoff_base_seconds=0.01))
    assert result == "ok"
    assert len(calls) == 1


def test_with_retry_retries_then_succeeds():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("transient")
        return "ok"

    result = asyncio.run(_with_retry(fn, retry_attempts=2, retry_backoff_base_seconds=0.01))
    assert result == "ok"
    assert len(calls) == 2


def test_with_retry_exhausts_attempts_and_raises_last_exception():
    calls = []

    async def fn():
        calls.append(1)
        raise RuntimeError(f"failure #{len(calls)}")

    with pytest.raises(RuntimeError, match="failure #3"):
        asyncio.run(_with_retry(fn, retry_attempts=2, retry_backoff_base_seconds=0.01))
    assert len(calls) == 3  # initial attempt + 2 retries


def test_with_retry_zero_attempts_means_single_try():
    calls = []

    async def fn():
        calls.append(1)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(_with_retry(fn, retry_attempts=0, retry_backoff_base_seconds=0.01))
    assert len(calls) == 1


def test_with_retry_backoff_grows_exponentially(monkeypatch):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("transient")
        return "ok"

    asyncio.run(_with_retry(fn, retry_attempts=3, retry_backoff_base_seconds=0.5))
    assert sleeps == [0.5, 1.0]


def test_call_mcp_tool_retries_on_connect_failure_then_succeeds(monkeypatch):
    """Full call_mcp_tool path (not just _with_retry in isolation):
    streamablehttp_client raising on the first attempt and succeeding on
    the second must surface as a successful call, not McpToolError.
    """
    attempts = {"count": 0}

    class _FakeContentBlock:
        type = "text"
        text = '{"provider": "mock", "hotels": []}'

    class _FakeResult:
        isError = False
        structuredContent = None
        content = [_FakeContentBlock()]

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def initialize(self):
            return None

        async def call_tool(self, tool_name, arguments, read_timeout_seconds=None):
            return _FakeResult()

    class _FakeStreamCtx:
        async def __aenter__(self):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ConnectionError("connection refused")
            return (None, None, None)

        async def __aexit__(self, *_exc):
            return False

    def fake_streamablehttp_client(url, timeout=None, sse_read_timeout=None):
        return _FakeStreamCtx()

    monkeypatch.setattr("app.mcp_client.streamablehttp_client", fake_streamablehttp_client)
    monkeypatch.setattr("app.mcp_client.ClientSession", lambda read, write: _FakeSession())

    result = asyncio.run(
        call_mcp_tool("http://mcp:9000/mcp", "search_hotels", {}, retry_attempts=2, retry_backoff_base_seconds=0.01)
    )
    assert result == {"provider": "mock", "hotels": []}
    assert attempts["count"] == 2


def test_call_mcp_tool_raises_mcptoolerror_after_exhausting_retries(monkeypatch):
    def fake_streamablehttp_client(url, timeout=None, sse_read_timeout=None):
        class _AlwaysFails:
            async def __aenter__(self):
                raise ConnectionError("connection refused")

            async def __aexit__(self, *_exc):
                return False

        return _AlwaysFails()

    monkeypatch.setattr("app.mcp_client.streamablehttp_client", fake_streamablehttp_client)

    with pytest.raises(McpToolError):
        asyncio.run(
            call_mcp_tool("http://mcp:9000/mcp", "search_hotels", {}, retry_attempts=1, retry_backoff_base_seconds=0.01)
        )
