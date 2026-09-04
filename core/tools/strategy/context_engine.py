"""Spatiotemporal Context Engine (DSH-08)
======================================
Pure Object-Oriented Programming (OOP) spatiotemporal composability engine.
Grounded in the Cordis context paradigm & DeepSeek Harness (@deepseek-ai/dsh).

Key Architectural Invariants:
1. Temporal (Revertible Effects):
   - Every state mutation yields an EffectDisposer.
   - Teardown executes disposers strictly in LIFO (Last-In, First-Out) order.
2. Spatial (Reactive Coeffects):
   - Consumers declare dependencies via ctx.inject(*keys).
   - Providers register dynamically and expose live health checks.
   - Provider health flips, additions, and removals fire Coeffect events that
     automatically refresh, activate, or degrade dependent fibers without restarts.
3. Strict Safety & Edge Case Handling:
   - Cycle detection for dependency graphs (CircularDependencyError).
   - Re-entrancy protection for cascading event dispatches.
   - Zero hardcoded switch/case statements.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
import threading
import time
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
)

logger = logging.getLogger("context_engine")

T = TypeVar("T")


# ── Exceptions ───────────────────────────────────────────────────────────────

class SpatiotemporalError(Exception):
    """Base exception for all spatiotemporal context errors."""
    pass


class CircularDependencyError(SpatiotemporalError):
    """Raised when an injected coeffect creates a cycle in the dependency graph."""
    pass


class ProviderResolutionError(SpatiotemporalError):
    """Raised when no provider is available to satisfy an active coeffect."""
    pass


# ── Lifecycle States & Event Tokens ──────────────────────────────────────────

class FiberState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISPOSED = "disposed"


class CoeffectEventType(str, Enum):
    PROVIDER_REGISTERED = "provider_registered"
    PROVIDER_UNREGISTERED = "provider_unregistered"
    HEALTH_CHANGED = "health_changed"
    VALUE_SET = "value_set"
    FIBER_REFRESHED = "fiber_refreshed"


@dataclass(frozen=True)
class ReactiveCoeffectEvent:
    event_type: CoeffectEventType
    key: str
    provider_name: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    timestamp: float = field(default_factory=time.time)


# ── Revertible Effect Disposer ───────────────────────────────────────────────

class EffectDisposer:
    """Encapsulates a reversible inverse callback executed on disposal."""

    def __init__(self, undo_fn: Callable[[], None], name: str = "anonymous_disposer"):
        self._undo_fn = undo_fn
        self._name = name
        self._disposed = False
        self._lock = threading.Lock()

    @property
    def is_disposed(self) -> bool:
        return self._disposed

    def dispose(self) -> None:
        """Executes the undo callback once. Idempotent."""
        with self._lock:
            if not self._disposed:
                self._disposed = True
                try:
                    self._undo_fn()
                except Exception as e:
                    logger.error(f"[DISPOSER] Error during undo for '{self._name}': {e}", exc_info=True)

    def __call__(self) -> None:
        self.dispose()

    def __repr__(self) -> str:
        return f"<EffectDisposer name='{self._name}' disposed={self._disposed}>"


# ── 3-Role Capability Seam (Definition & Provider) ───────────────────────────

class CapabilityDefinition(Generic[T]):
    """Role 1: Service Definition — declares the capability contract and protocol."""

    def __init__(
        self,
        name: str,
        description: str = "",
        protocol_class: Optional[Type[T]] = None,
        version: str = "1.0.0",
    ):
        self.name = name.strip()
        self.description = description
        self.protocol_class = protocol_class
        self.version = version

    def validate_instance(self, instance: Any) -> bool:
        """Validates that a provider's instance conforms to this definition."""
        if self.protocol_class is None:
            return True
        return isinstance(instance, self.protocol_class)

    def __repr__(self) -> str:
        return f"<CapabilityDefinition '{self.name}' v{self.version}>"


class CapabilityProvider(Generic[T], ABC):
    """Role 2: Service Provider — abstract base class for capability implementations."""

    def __init__(self, name: str, capability_name: str, priority: int = 100):
        self.name = name.strip()
        self.capability_name = capability_name.strip()
        self.priority = priority
        self._last_health_state: Optional[bool] = None

    @abstractmethod
    def is_healthy(self) -> bool:
        """Returns True if this provider is currently available and functioning."""
        pass

    @abstractmethod
    def get_instance(self) -> T:
        """Returns the underlying service instance or client."""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Provides operational metadata for telemetry and diagnostics."""
        return {
            "name": self.name,
            "capability_name": self.capability_name,
            "priority": self.priority,
            "healthy": self.is_healthy(),
        }

    def __repr__(self) -> str:
        return f"<CapabilityProvider '{self.name}' for '{self.capability_name}' (priority={self.priority})>"


# ── Reactive Fiber (Role 3: Consumer) ────────────────────────────────────────

class ReactiveFiber:
    """Role 3: Consumer / Subscriber Fiber.

    Declares injected capability keys. When provider states or context values
    change, the fiber refreshes its resolved dependencies and notifies listeners.
    """

    def __init__(
        self,
        fiber_id: str,
        dependencies: Set[str],
        on_change: Optional[Callable[[ReactiveCoeffectEvent], None]] = None,
    ):
        self.fiber_id = fiber_id
        self.dependencies = set(dependencies)
        self.on_change = on_change
        self.state = FiberState.PENDING
        self.resolved_providers: Dict[str, CapabilityProvider] = {}
        self.resolved_values: Dict[str, Any] = {}
        self._disposers: List[EffectDisposer] = []
        self._lock = threading.RLock()

    def add_disposer(self, disposer: EffectDisposer) -> None:
        """Tracks an effect disposer local to this fiber."""
        with self._lock:
            self._disposers.append(disposer)

    def refresh(self, engine: ContextEngine) -> None:
        """Evaluates injected dependencies against the engine and updates state."""
        with self._lock:
            if self.state == FiberState.DISPOSED:
                return

            all_healthy = True
            new_resolved: Dict[str, CapabilityProvider] = {}
            new_values: Dict[str, Any] = {}

            for dep in self.dependencies:
                # 1. Try resolving capability provider
                prov = engine.resolve(dep)
                if prov is not None and prov.is_healthy():
                    new_resolved[dep] = prov
                else:
                    # 2. Try resolving direct context key-value
                    val = engine.get(dep, None)
                    if val is not None:
                        new_values[dep] = val
                    else:
                        all_healthy = False

            self.resolved_providers = new_resolved
            self.resolved_values = new_values

            old_state = self.state
            if all_healthy and (len(new_resolved) + len(new_values) == len(self.dependencies)):
                self.state = FiberState.ACTIVE
            else:
                self.state = FiberState.DEGRADED

            if old_state != self.state:
                logger.info(f"[FIBER] Fiber '{self.fiber_id}' state transition: {old_state.value} -> {self.state.value}")

    def notify(self, event: ReactiveCoeffectEvent) -> None:
        """Dispatches an event to the consumer hook if registered."""
        if self.on_change and self.state != FiberState.DISPOSED:
            try:
                self.on_change(event)
            except Exception as e:
                logger.error(f"[FIBER] Error in fiber '{self.fiber_id}' on_change handler: {e}", exc_info=True)

    def dispose(self) -> None:
        """Unwinds fiber local effects in LIFO order."""
        with self._lock:
            self.state = FiberState.DISPOSED
            while self._disposers:
                disp = self._disposers.pop()
                disp.dispose()
            self.resolved_providers.clear()
            self.resolved_values.clear()

    def __repr__(self) -> str:
        return f"<ReactiveFiber '{self.fiber_id}' state={self.state.value} deps={list(self.dependencies)}>"


# ── Context Engine (The Spatiotemporal Coordinator) ──────────────────────────

class ContextEngine:
    """The central Spatiotemporal Context Coordinator.

    Manages dynamic capability definitions, provider priorities, reactive fibers,
    LIFO revertible effects, and circular dependency safety.
    """

    def __init__(self, name: str = "KenbunSovereignContext"):
        self.name = name
        self._definitions: Dict[str, CapabilityDefinition] = {}
        self._providers: Dict[str, List[CapabilityProvider]] = {}
        self._fibers: Dict[str, ReactiveFiber] = {}
        self._values: Dict[str, Any] = {}
        self._dependencies: Dict[str, Set[str]] = {}  # fiber_id -> set of dependencies
        self._global_disposers: List[EffectDisposer] = []
        
        # Concurrency & Re-entrancy guards
        self._lock = threading.RLock()
        self._event_queue: List[ReactiveCoeffectEvent] = []
        self._is_dispatching = False

    # ── Definition Registration ──────────────────────────────────────────────

    def define_capability(self, definition: CapabilityDefinition[T]) -> EffectDisposer:
        """Registers a capability definition. Returns a LIFO disposer."""
        with self._lock:
            cap_name = definition.name
            if cap_name in self._definitions:
                logger.warning(f"[CONTEXT] Overwriting definition for '{cap_name}'.")

            self._definitions[cap_name] = definition

            def _undo():
                with self._lock:
                    if self._definitions.get(cap_name) == definition:
                        del self._definitions[cap_name]
                        logger.info(f"[CONTEXT] Unregistered capability definition '{cap_name}'.")

            disposer = EffectDisposer(_undo, name=f"undefine_cap_{cap_name}")
            self._global_disposers.append(disposer)
            return disposer

    # ── Dynamic Provider Registration ─────────────────────────────────────────

    def register_provider(
        self,
        definition: CapabilityDefinition[T],
        provider: CapabilityProvider[T],
    ) -> EffectDisposer:
        """Registers a concrete provider for a capability.

        Ensures zero-hardcoding: providers are sorted dynamically by priority.
        Automatically notifies dependent fibers and returns a LIFO disposer.
        """
        with self._lock:
            cap_name = definition.name
            if cap_name not in self._definitions:
                self.define_capability(definition)

            if cap_name not in self._providers:
                self._providers[cap_name] = []

            # Add provider and sort by priority (highest first)
            self._providers[cap_name].append(provider)
            self._providers[cap_name].sort(key=lambda p: p.priority, reverse=True)

            # Initialize health baseline state
            try:
                provider._last_health_state = provider.is_healthy()
            except Exception:
                provider._last_health_state = False

            logger.info(f"[CONTEXT] Registered provider '{provider.name}' for capability '{cap_name}' (priority={provider.priority})")

            # Fire reactive coeffect event
            event = ReactiveCoeffectEvent(
                event_type=CoeffectEventType.PROVIDER_REGISTERED,
                key=cap_name,
                provider_name=provider.name,
                new_value=provider,
            )
            self._enqueue_and_dispatch(event)

            def _undo():
                with self._lock:
                    if cap_name in self._providers and provider in self._providers[cap_name]:
                        self._providers[cap_name].remove(provider)
                        logger.info(f"[CONTEXT] Unregistered provider '{provider.name}' from capability '{cap_name}'.")
                        
                        unreg_event = ReactiveCoeffectEvent(
                            event_type=CoeffectEventType.PROVIDER_UNREGISTERED,
                            key=cap_name,
                            provider_name=provider.name,
                        )
                        self._enqueue_and_dispatch(unreg_event)

            disposer = EffectDisposer(_undo, name=f"unregister_{provider.name}")
            self._global_disposers.append(disposer)
            return disposer

    # ── Direct Spatial Context Key-Values ─────────────────────────────────────

    def set(self, key: str, value: Any) -> EffectDisposer:
        """Sets a reactive context key-value pair. Returns a LIFO disposer."""
        with self._lock:
            old_val = self._values.get(key)
            self._values[key] = value

            event = ReactiveCoeffectEvent(
                event_type=CoeffectEventType.VALUE_SET,
                key=key,
                old_value=old_val,
                new_value=value,
            )
            self._enqueue_and_dispatch(event)

            def _undo():
                with self._lock:
                    if self._values.get(key) == value:
                        if old_val is not None:
                            self._values[key] = old_val
                        else:
                            del self._values[key]
                        
                        rev_event = ReactiveCoeffectEvent(
                            event_type=CoeffectEventType.VALUE_SET,
                            key=key,
                            old_value=value,
                            new_value=old_val,
                        )
                        self._enqueue_and_dispatch(rev_event)

            disposer = EffectDisposer(_undo, name=f"unset_{key}")
            self._global_disposers.append(disposer)
            return disposer

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a direct context value."""
        with self._lock:
            return self._values.get(key, default)

    # ── Capability Provider Resolution ────────────────────────────────────────

    def resolve(self, capability_name: str) -> Optional[CapabilityProvider[Any]]:
        """Resolves the highest-priority healthy provider for a capability."""
        with self._lock:
            providers = self._providers.get(capability_name, [])
            for prov in providers:
                try:
                    if prov.is_healthy():
                        return prov
                except Exception as e:
                    logger.warning(f"[CONTEXT] Provider '{prov.name}' health check failed: {e}")
            return None

    def resolve_all_healthy(self, capability_name: str) -> List[CapabilityProvider[Any]]:
        """Resolves all currently healthy providers in priority order."""
        with self._lock:
            providers = self._providers.get(capability_name, [])
            healthy = []
            for prov in providers:
                try:
                    if prov.is_healthy():
                        healthy.append(prov)
                except Exception:
                    pass
            return healthy

    # ── Coeffect Injection (Fiber Subscription) ───────────────────────────────

    def inject(
        self,
        fiber_id: str,
        dependencies: Set[str],
        on_change: Optional[Callable[[ReactiveCoeffectEvent], None]] = None,
    ) -> ReactiveFiber:
        """Creates a reactive subscriber fiber with injected dependencies.

        Performs cycle detection to prevent circular deadlocks.
        """
        with self._lock:
            # 1. Cycle detection guard
            self._check_circular_dependencies(fiber_id, dependencies)

            # 2. Register fiber
            fiber = ReactiveFiber(fiber_id, dependencies, on_change)
            self._fibers[fiber_id] = fiber
            self._dependencies[fiber_id] = set(dependencies)

            # 3. Initial evaluation
            fiber.refresh(self)

            logger.info(f"[CONTEXT] Fiber '{fiber_id}' created with state: {fiber.state.value}")
            return fiber

    def uninject(self, fiber_id: str) -> None:
        """Removes and disposes a reactive fiber."""
        with self._lock:
            if fiber_id in self._fibers:
                fiber = self._fibers.pop(fiber_id)
                fiber.dispose()
            if fiber_id in self._dependencies:
                del self._dependencies[fiber_id]
            logger.info(f"[CONTEXT] Fiber '{fiber_id}' disposed and uninjected.")

    # ── Circular Dependency Cycle Detection ───────────────────────────────────

    def _check_circular_dependencies(self, new_fiber_id: str, new_deps: Set[str]) -> None:
        """Detects if adding new_fiber_id creates a cycle using DFS."""
        graph: Dict[str, Set[str]] = dict(self._dependencies)
        graph[new_fiber_id] = set(new_deps)

        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def _dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, set()):
                # Only check nodes that are also registered fibers
                if neighbor in graph:
                    if neighbor not in visited:
                        if _dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if _dfs(node):
                    raise CircularDependencyError(
                        f"Circular dependency cycle detected involving fiber '{new_fiber_id}' and dependency '{node}'."
                    )

    # ── Temporal Effects Helper ───────────────────────────────────────────────

    def effect(
        self,
        apply_fn: Callable[[], Any],
        undo_fn: Callable[[], None],
        name: str = "custom_effect",
    ) -> EffectDisposer:
        """Executes an effect and records its LIFO undo disposer."""
        with self._lock:
            apply_fn()
            disposer = EffectDisposer(undo_fn, name=name)
            self._global_disposers.append(disposer)
            return disposer

    # ── Reactive Dispatch Pipeline ────────────────────────────────────────────

    def _enqueue_and_dispatch(self, event: ReactiveCoeffectEvent) -> None:
        """Queues an event and dispatches to dependent fibers with re-entrancy protection."""
        self._event_queue.append(event)

        if self._is_dispatching:
            return  # Queued for current loop to process

        self._is_dispatching = True
        try:
            while self._event_queue:
                current_event = self._event_queue.pop(0)
                affected_key = current_event.key

                # Find all fibers that depend on the affected key
                for fiber in list(self._fibers.values()):
                    if affected_key in fiber.dependencies:
                        fiber.refresh(self)
                        fiber.notify(current_event)
        finally:
            self._is_dispatching = False

    def poll_health_and_dispatch(self) -> int:
        """Polls provider health states and fires HEALTH_CHANGED events on transitions.

        Returns count of transitions detected.
        """
        transitions = 0
        with self._lock:
            for cap_name, prov_list in self._providers.items():
                for prov in prov_list:
                    current_health = prov.is_healthy()
                    if prov._last_health_state is not None and prov._last_health_state != current_health:
                        transitions += 1
                        logger.warning(
                            f"[CONTEXT] Provider '{prov.name}' for '{cap_name}' health flipped: "
                            f"{prov._last_health_state} -> {current_health}"
                        )
                        event = ReactiveCoeffectEvent(
                            event_type=CoeffectEventType.HEALTH_CHANGED,
                            key=cap_name,
                            provider_name=prov.name,
                            old_value=prov._last_health_state,
                            new_value=current_health,
                        )
                        self._enqueue_and_dispatch(event)
                    prov._last_health_state = current_health
        return transitions

    # ── Teardown & Reset ──────────────────────────────────────────────────────

    def dispose_all(self) -> None:
        """Executes all global disposers in strict LIFO order."""
        with self._lock:
            logger.info(f"[CONTEXT] Executing {len(self._global_disposers)} disposers in LIFO order...")
            while self._global_disposers:
                disp = self._global_disposers.pop()
                disp.dispose()

            for fiber in list(self._fibers.values()):
                fiber.dispose()
            self._fibers.clear()
            self._providers.clear()
            self._definitions.clear()
            self._values.clear()
            self._dependencies.clear()

    # ── Telemetry & Observability ─────────────────────────────────────────────

    def get_resilience_status(self) -> Dict[str, Any]:
        """Observability telemetry for the Observatory and health sentinels."""
        with self._lock:
            cap_summary = {}
            for cap_name, provs in self._providers.items():
                healthy_count = sum(1 for p in provs if p.is_healthy())
                cap_summary[cap_name] = {
                    "total_providers": len(provs),
                    "healthy_providers": healthy_count,
                    "active_provider": provs[0].name if healthy_count > 0 else None,
                    "is_spof": len(provs) == 1,
                    "providers": [p.get_metadata() for p in provs],
                }

            fiber_summary = {
                f_id: {
                    "state": f.state.value,
                    "dependencies": list(f.dependencies),
                    "resolved": list(f.resolved_providers.keys()),
                }
                for f_id, f in self._fibers.items()
            }

            return {
                "engine_name": self.name,
                "capabilities": cap_summary,
                "fibers": fiber_summary,
                "context_values_count": len(self._values),
                "active_disposers_count": len(self._global_disposers),
            }


# Global Default Singleton Instance
sovereign_context = ContextEngine()
