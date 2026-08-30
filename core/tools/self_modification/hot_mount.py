"""DSH-05 slice 1 -- mount a tool into the running swarm, revert it on guard failure.

    from tools.self_modification import guarded_mount

    def my_new_tool(x: int) -> str:
        "adds one"
        return str(x + 1)

    res = guarded_mount(my_new_tool, name="add_one",
                        guard=lambda fn: fn(1) == "2")
    if res.guard_passed:
        ...            # tool is live in the registry AND the FastMCP surface
    # if the guard failed, res.reverted is True and the registry is untouched

No process restart either way. This is the loop `agent_self_improve` needs: try a
candidate tool against a smoke check, keep it if it works, drop it if it does not.

**Trust boundary.** `hot_mount_tool` takes an *already-defined Python callable*,
not source text -- it does not `exec` anything. Turning generated source into a
callable safely (sandbox / subprocess / import allowlist) is a separate step and
a later slice; this module assumes the callable it is handed came from Kenbun's
own generation pipeline, never from a tool argument or routed model/user input.

**Known limitation.** `bayesian._known_tool_ids()` is cached from the last
harvest, so a hot-mounted tool is invisible to routing telemetry until a fresh
harvest runs -- `tune_swarm` logs "rejecting unknown tool_id" and skips the write
(by design: keeps probe/self-mod tools out of the real Bayesian store). Wiring a
cache-refresh hook into `hot_mount_tool` is a later slice.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, List, Optional

logger = logging.getLogger("kenbun.self_modification")


class HotMountError(RuntimeError):
    """The callable could not be mounted as a sovereign tool."""


@dataclass(frozen=True)
class MountResult:
    name: str
    mounted: bool                       # did it get into the registry at all
    reverted: bool                      # was it then removed by the guard failing
    guard_passed: Optional[bool]        # None if the guard never ran
    error: Optional[str] = None
    # Set only while the tool is still live (guard passed, or revert failed). The
    # CALLER owns this handle: losing the reference without calling it leaves the
    # tool mounted for the life of the process.
    dispose: Optional[Callable[[], None]] = None


def hot_mount_tool(
    fn: Callable,
    *,
    name: str,
    category: str = "SelfMod",
    requires_env: Optional[List[str]] = None,
) -> tuple[Callable, Callable[[], None]]:
    """Register ``fn`` as a live sovereign tool. Returns ``(wrapped, disposer)``.

    Reuses the ``sovereign_tool`` decorator, so the mounted tool gets the same
    stdout guard, surrogate sanitisation, and outcome telemetry as any other --
    and ``wrapped._sovereign_disposer`` (DSH-01) removes it: from the registry,
    and via server.py's listener, from the live FastMCP tool list.
    """
    if not callable(fn):
        raise HotMountError(f"{name!r}: object is not callable")

    from tools.registry import sovereign_tool

    # exclusive=True: the "is this name free?" check and the insert happen under
    # one registry-lock hold, so two racing hot-mounts of the same name cannot
    # both register and leak a disposer.
    try:
        wrapped = sovereign_tool(
            name=name, category=category, requires_env=requires_env or [], exclusive=True,
        )(fn)
    except KeyError as e:
        raise HotMountError(str(e)) from e
    disposer = getattr(wrapped, "_sovereign_disposer", None)
    if disposer is None:  # pragma: no cover -- DSH-01 guarantees this attr
        from tools.registry import registry
        disposer = lambda: registry.unregister_tool(name)  # noqa: E731
    logger.info("hot_mount: tool %r mounted into the running registry", name)
    return wrapped, disposer


def guarded_mount(
    fn: Callable,
    *,
    name: str,
    guard: Callable[[Callable], bool],
    category: str = "SelfMod",
    requires_env: Optional[List[str]] = None,
) -> MountResult:
    """Mount ``fn``, run ``guard(wrapped)``, and auto-revert unless the guard
    returns truthy. The guard is where a self-improvement pipeline puts its smoke
    check (call the tool on a probe input, assert the shape of the result, ...).
    """
    try:
        wrapped, dispose = hot_mount_tool(
            fn, name=name, category=category, requires_env=requires_env,
        )
    except Exception as e:
        logger.warning("guarded_mount: %r failed to mount: %s", name, e)
        return MountResult(name=name, mounted=False, reverted=False,
                           guard_passed=None, error=str(e))

    try:
        passed = bool(guard(wrapped))
    except Exception as e:
        return _revert(name, dispose, why=f"guard raised: {e}")

    if not passed:
        return _revert(name, dispose, why="guard returned falsy")

    logger.info("guarded_mount: %r passed its guard and stays live", name)
    return MountResult(name=name, mounted=True, reverted=False,
                       guard_passed=True, dispose=dispose)


def _revert(name: str, dispose: Callable[[], None], *, why: str) -> MountResult:
    """Run the disposer for a mount the guard rejected. If the revert itself
    fails, say so plainly (`reverted=False`) and hand back the disposer -- the
    caller must know the tool may still be live rather than assume it is gone."""
    try:
        dispose()
    except Exception as e:
        logger.error("guarded_mount: %r REVERT FAILED after %s: %s -- tool may still be live",
                     name, why, e)
        return MountResult(name=name, mounted=True, reverted=False, guard_passed=False,
                           error=f"{why}; revert failed: {e}", dispose=dispose)
    logger.info("guarded_mount: %r reverted (%s)", name, why)
    return MountResult(name=name, mounted=True, reverted=True, guard_passed=False, error=why)
