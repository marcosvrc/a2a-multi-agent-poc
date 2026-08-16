import os

import pytest

os.environ.setdefault("OTEL_SDK_DISABLED", "true")


@pytest.fixture(autouse=True)
def _reset_circuit_breakers():
    """`app.agent.circuit_breakers` is a module-level singleton (one
    breaker per agent id, shared across every request the running Planner
    handles — that's the point in production). In tests, though, agent
    ids like "flight-agent" repeat across test functions, so without a
    reset a breaker OPENed by one test's deliberate failures would still
    be OPEN for a later, unrelated test using the same agent id — a
    classic shared-mutable-module-state test-pollution bug. Reset before
    every test so each one starts with a clean slate (Fase 8, §27/§35).
    """
    from app import agent as agent_module
    from app.resilience import CircuitBreakerRegistry

    agent_module.circuit_breakers = CircuitBreakerRegistry(
        failure_threshold=agent_module.settings.circuit_breaker_failure_threshold,
        reset_timeout_seconds=agent_module.settings.circuit_breaker_reset_timeout_seconds,
    )
    yield
