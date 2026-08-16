"""Unit tests for app/resilience.py (Fase 8, §27/§35): the CircuitBreaker
state machine in isolation, independent of the Planner/A2A wiring covered
in test_agent.py's CT-R0x tests.
"""
from __future__ import annotations

import time

from app.resilience import CircuitBreaker, CircuitBreakerRegistry, CircuitState


def test_starts_closed_and_allows_requests():
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=30)
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow_request() is True


def test_stays_closed_below_failure_threshold():
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=30)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow_request() is True


def test_opens_after_reaching_failure_threshold():
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=30)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow_request() is False


def test_success_resets_consecutive_failure_count():
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=30)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()
    # Only 2 consecutive failures since the last success — still CLOSED.
    assert breaker.state is CircuitState.CLOSED


def test_transitions_to_half_open_after_cooldown_and_recovers_on_success():
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout_seconds=0.05)
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow_request() is False

    time.sleep(0.06)
    assert breaker.state is CircuitState.HALF_OPEN
    # Exactly one trial call is let through...
    assert breaker.allow_request() is True
    # ...and a second concurrent caller must not also get a trial slot.
    assert breaker.allow_request() is False

    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow_request() is True


def test_half_open_trial_failure_reopens_and_restarts_cooldown():
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout_seconds=0.05)
    breaker.record_failure()
    time.sleep(0.06)
    assert breaker.state is CircuitState.HALF_OPEN
    assert breaker.allow_request() is True

    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow_request() is False


def test_registry_returns_same_breaker_instance_for_same_agent_id():
    registry = CircuitBreakerRegistry(failure_threshold=3, reset_timeout_seconds=30)
    a = registry.get("flight-agent")
    b = registry.get("flight-agent")
    assert a is b


def test_registry_isolates_breakers_per_agent_id():
    registry = CircuitBreakerRegistry(failure_threshold=1, reset_timeout_seconds=30)
    flight = registry.get("flight-agent")
    hotel = registry.get("hotel-agent")

    flight.record_failure()
    assert flight.state is CircuitState.OPEN
    # A different agent's breaker must be entirely unaffected.
    assert hotel.state is CircuitState.CLOSED
    assert hotel.allow_request() is True
