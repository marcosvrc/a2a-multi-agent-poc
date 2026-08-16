"""Resilience primitives (PROJECT_SPEC.md §27/§35, Fase 8): a per-agent
circuit breaker applied at the Planner -> specialist A2A boundary.

Retry-with-exponential-backoff for *transient transport* failures
(timeout, connection refused, 5xx) lives in `app/a2a/client.py` itself
(`A2AClient._post_with_retry`), since it operates below the level of a
single HTTP POST. What lives here is the layer above: deciding, before
ever attempting a call, whether a specialist that has recently failed
repeatedly should be tried again at all.

Not repeating non-idempotent calls without control (§27): the retry
inside `A2AClient` only fires on transport-level failures — no evidence
the specialist ever received or processed the request. A JSON-RPC-level
error (`A2AClientError`, meaning the specialist *did* answer, just with
an error) is never retried and always counts as a circuit-breaker
failure exactly once, never more.
"""
from __future__ import annotations

import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Per-agent circuit breaker.

    CLOSED (normal): every call is attempted.
    OPEN: after `failure_threshold` consecutive failures, calls are
    short-circuited (no network round-trip at all) for
    `reset_timeout_seconds` — this is what makes a definitely-down
    specialist stop costing every subsequent request a full timeout.
    HALF_OPEN: once the cooldown elapses, exactly one trial call is
    allowed through; success closes the breaker, failure re-opens it
    and restarts the cooldown.
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: float = 30.0) -> None:
        self._failure_threshold = max(failure_threshold, 1)
        self._reset_timeout_seconds = reset_timeout_seconds
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        # Set only while a HALF_OPEN trial call is in flight, so a second
        # concurrent caller doesn't also sneak a trial call through before
        # the first one reports back.
        self._trial_in_flight = False

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN and self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self._reset_timeout_seconds:
                return CircuitState.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        current = self.state
        if current is CircuitState.OPEN:
            return False
        if current is CircuitState.HALF_OPEN:
            if self._trial_in_flight:
                return False
            self._trial_in_flight = True
            return True
        return True

    def record_success(self) -> None:
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None
        self._trial_in_flight = False

    def record_failure(self) -> None:
        self._trial_in_flight = False
        self._consecutive_failures += 1
        if self._state is CircuitState.HALF_OPEN or self._consecutive_failures >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()


class CircuitBreakerRegistry:
    """One CircuitBreaker per agent id, created lazily on first use."""

    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: float = 30.0) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout_seconds = reset_timeout_seconds
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, agent_id: str) -> CircuitBreaker:
        breaker = self._breakers.get(agent_id)
        if breaker is None:
            breaker = CircuitBreaker(self._failure_threshold, self._reset_timeout_seconds)
            self._breakers[agent_id] = breaker
        return breaker
