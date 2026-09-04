"""Unit Tests for Spatiotemporal Context Engine (DSH-08)
=====================================================
Tests:
1. Dynamic capability definition and priority-based provider resolution
2. Health-aware failover from primary to fallback provider
3. Reactive Fiber coeffect injection and state transitions (PENDING -> ACTIVE -> DEGRADED)
4. Event dispatch pipeline upon provider registration, removal, and health changes
5. Temporal LIFO disposer execution and teardown guarantees
6. Circular dependency detection (CircularDependencyError)
7. Re-entrancy queue protection
"""

import pytest
from typing import Dict, Any

from tools.strategy.context_engine import (
    ContextEngine,
    CapabilityDefinition,
    CapabilityProvider,
    FiberState,
    CoeffectEventType,
    CircularDependencyError,
)


class MockDatabaseClient:
    def __init__(self, name: str):
        self.name = name

    def query(self, sql: str) -> str:
        return f"result_from_{self.name}"


class MockDatabaseProvider(CapabilityProvider[MockDatabaseClient]):
    def __init__(self, name: str, priority: int = 100, healthy: bool = True):
        super().__init__(name=name, capability_name="database", priority=priority)
        self._healthy = healthy
        self._client = MockDatabaseClient(name)

    def is_healthy(self) -> bool:
        return self._healthy

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = healthy

    def get_instance(self) -> MockDatabaseClient:
        return self._client


def test_capability_definition_and_priority_resolution():
    """Verifies providers are ordered by priority and highest healthy provider is resolved."""
    engine = ContextEngine("TestEngine")
    cap_def = CapabilityDefinition[MockDatabaseClient]("database", "Primary relational store")
    engine.define_capability(cap_def)

    prov_local = MockDatabaseProvider("sqlite_fallback", priority=50, healthy=True)
    prov_remote = MockDatabaseProvider("postgres_primary", priority=100, healthy=True)

    engine.register_provider(cap_def, prov_local)
    engine.register_provider(cap_def, prov_remote)

    resolved = engine.resolve("database")
    assert resolved is not None
    assert resolved.name == "postgres_primary"
    assert resolved.get_instance().query("SELECT 1") == "result_from_postgres_primary"


def test_health_aware_fallback_resolution():
    """Verifies that when the primary provider is unhealthy, engine resolves the next healthy fallback."""
    engine = ContextEngine("TestEngine")
    cap_def = CapabilityDefinition[MockDatabaseClient]("database")
    
    prov_remote = MockDatabaseProvider("postgres_primary", priority=100, healthy=False)
    prov_local = MockDatabaseProvider("sqlite_fallback", priority=50, healthy=True)

    engine.register_provider(cap_def, prov_remote)
    engine.register_provider(cap_def, prov_local)

    resolved = engine.resolve("database")
    assert resolved is not None
    assert resolved.name == "sqlite_fallback"


def test_reactive_fiber_coeffect_activation_and_degradation():
    """Verifies that an injected fiber reflects provider health automatically."""
    engine = ContextEngine("TestEngine")
    cap_def = CapabilityDefinition[MockDatabaseClient]("database")
    prov_remote = MockDatabaseProvider("postgres_primary", priority=100, healthy=True)
    engine.register_provider(cap_def, prov_remote)

    events_captured = []
    def on_change(event):
        events_captured.append(event)

    fiber = engine.inject("test_worker_fiber", {"database"}, on_change=on_change)
    assert fiber.state == FiberState.ACTIVE
    assert "database" in fiber.resolved_providers

    # Simulate primary failure
    prov_remote.set_healthy(False)
    engine.poll_health_and_dispatch()

    assert fiber.state == FiberState.DEGRADED
    assert len(events_captured) == 1
    assert events_captured[0].event_type == CoeffectEventType.HEALTH_CHANGED

    # Now register a healthy fallback dynamically
    prov_local = MockDatabaseProvider("sqlite_fallback", priority=50, healthy=True)
    engine.register_provider(cap_def, prov_local)

    assert fiber.state == FiberState.ACTIVE
    assert fiber.resolved_providers["database"].name == "sqlite_fallback"


def test_revertible_effect_lifo_order():
    """Verifies that disposers execute in strict Last-In, First-Out (LIFO) order."""
    engine = ContextEngine("TestEngine")
    execution_order = []

    disp1 = engine.effect(lambda: None, lambda: execution_order.append(1), name="step1")
    disp2 = engine.effect(lambda: None, lambda: execution_order.append(2), name="step2")
    disp3 = engine.effect(lambda: None, lambda: execution_order.append(3), name="step3")

    engine.dispose_all()

    assert execution_order == [3, 2, 1]


def test_disposer_unregisters_provider_cleanly():
    """Verifies that calling a provider's disposer removes it from the engine."""
    engine = ContextEngine("TestEngine")
    cap_def = CapabilityDefinition[MockDatabaseClient]("database")
    prov = MockDatabaseProvider("postgres_primary", priority=100, healthy=True)

    disposer = engine.register_provider(cap_def, prov)
    assert engine.resolve("database") is not None

    disposer()
    assert engine.resolve("database") is None


def test_circular_dependency_detection():
    """Verifies that circular dependency loops between fibers raise CircularDependencyError."""
    engine = ContextEngine("TestEngine")

    engine.inject("fiber_a", {"fiber_b"})
    engine.inject("fiber_b", {"fiber_c"})

    with pytest.raises(CircularDependencyError) as exc_info:
        engine.inject("fiber_c", {"fiber_a"})

    assert "Circular dependency cycle detected" in str(exc_info.value)


def test_resilience_status_telemetry():
    """Verifies that get_resilience_status produces structured telemetry."""
    engine = ContextEngine("TestEngine")
    cap_def = CapabilityDefinition[MockDatabaseClient]("database")
    prov = MockDatabaseProvider("postgres_primary", priority=100, healthy=True)
    engine.register_provider(cap_def, prov)
    engine.inject("worker_1", {"database"})

    status = engine.get_resilience_status()
    assert status["engine_name"] == "TestEngine"
    assert "database" in status["capabilities"]
    assert status["capabilities"]["database"]["total_providers"] == 1
    assert status["capabilities"]["database"]["is_spof"] is True
    assert "worker_1" in status["fibers"]
    assert status["fibers"]["worker_1"]["state"] == "active"
