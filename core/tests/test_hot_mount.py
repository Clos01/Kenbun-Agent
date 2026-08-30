"""DSH-05 slice 1 -- mount a tool into the running swarm, revert on guard failure, no restart."""
import threading

import pytest

from tools.registry import registry
from tools.self_modification import MountResult, guarded_mount, hot_mount_tool


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for n in ("dsh05_good", "dsh05_bad", "dsh05_raises", "dsh05_probe",
              "dsh05_dup", "dsh05_race", "dsh05_revfail"):
        registry.unregister_tool(n)


def _good(x: int) -> str:
    """adds one"""
    return str(x + 1)


# --------------------------------------------------------------- hot_mount_tool
def test_hot_mount_puts_a_live_tool_in_the_registry():
    assert registry.get_tool("dsh05_probe") is None
    wrapped, dispose = hot_mount_tool(_good, name="dsh05_probe")
    try:
        entry = registry.get_tool("dsh05_probe")
        assert entry is not None
        assert entry.handler(41) == "42"      # the mounted tool is callable through the registry
        assert wrapped(41) == "42"
    finally:
        dispose()
    assert registry.get_tool("dsh05_probe") is None      # disposer removed it, no restart


def test_hot_mount_rejects_a_duplicate_name():
    _, dispose = hot_mount_tool(_good, name="dsh05_dup")
    try:
        with pytest.raises(Exception):
            hot_mount_tool(_good, name="dsh05_dup")
    finally:
        dispose()


def test_hot_mount_rejects_a_non_callable():
    with pytest.raises(Exception):
        hot_mount_tool(42, name="dsh05_probe")  # type: ignore[arg-type]


def test_concurrent_hot_mounts_of_one_name_do_not_both_win():
    """The exclusive check-and-insert is atomic: exactly one of N racing mounts
    of the same name succeeds; the others raise and leak no registration."""
    results: list = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            _, dispose = hot_mount_tool(_good, name="dsh05_race")
            results.append(("ok", dispose))
        except Exception as e:
            results.append(("err", e))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    wins = [r for r in results if r[0] == "ok"]
    assert len(wins) == 1
    assert registry.get_tool("dsh05_race") is not None
    wins[0][1]()                                   # dispose the winner
    assert registry.get_tool("dsh05_race") is None


# ---------------------------------------------------------------- guarded_mount
def test_guarded_mount_keeps_a_tool_that_passes_its_guard():
    res = guarded_mount(_good, name="dsh05_good", guard=lambda fn: fn(1) == "2")
    assert isinstance(res, MountResult)
    assert res.mounted and res.guard_passed and not res.reverted
    assert registry.get_tool("dsh05_good") is not None
    res.dispose()
    assert registry.get_tool("dsh05_good") is None


def test_guarded_mount_reverts_a_tool_whose_guard_returns_false():
    res = guarded_mount(_good, name="dsh05_bad", guard=lambda fn: fn(1) == "999")
    assert res.mounted and res.reverted
    assert res.guard_passed is False
    assert res.dispose is None
    assert registry.get_tool("dsh05_bad") is None        # auto-reverted, registry clean


def test_guarded_mount_reverts_a_tool_whose_guard_raises():
    def boom(fn):
        raise ValueError("smoke check exploded")

    res = guarded_mount(_good, name="dsh05_raises", guard=boom)
    assert res.reverted and res.guard_passed is False
    assert "guard raised" in res.error
    assert registry.get_tool("dsh05_raises") is None


def test_guarded_mount_reports_honestly_when_the_revert_itself_fails():
    """If the disposer raises, the result must NOT claim the tool is gone --
    the caller gets reverted=False and the disposer handle back."""
    from tools.self_modification.hot_mount import _revert

    def boom():
        raise RuntimeError("listener chain exploded")

    r = _revert("dsh05_revfail", boom, why="guard returned falsy")
    assert r.reverted is False
    assert "revert failed" in r.error
    assert r.dispose is boom


def test_guarded_mount_reports_a_mount_failure_without_reverting():
    _, dispose = hot_mount_tool(_good, name="dsh05_dup")
    try:
        res = guarded_mount(_good, name="dsh05_dup", guard=lambda fn: True)
        assert not res.mounted and not res.reverted
        assert res.guard_passed is None
    finally:
        dispose()


def test_a_reverted_tool_leaves_no_trace_in_get_all_tools():
    before = set(registry.get_all_tools())
    guarded_mount(_good, name="dsh05_bad", guard=lambda fn: False)
    assert set(registry.get_all_tools()) == before


def test_hot_mounted_tool_reaches_the_live_fastmcp_surface_and_leaves_on_revert():
    """DSH-05 end-to-end: a tool mounted after server startup shows up in
    mcp.list_tools with no restart, and a guard-reverted one never does."""
    import anyio

    import tools.infrastructure.server as server

    def names():
        return {t.name for t in anyio.run(server.mcp.list_tools)}

    assert "dsh05_probe" not in names()
    res = guarded_mount(_good, name="dsh05_probe", guard=lambda fn: fn(1) == "2")
    try:
        assert res.guard_passed
        assert "dsh05_probe" in names()        # <-- arrived live, no restart
    finally:
        res.dispose()
    assert "dsh05_probe" not in names()        # <-- disposer pulled it from MCP too

    guarded_mount(_good, name="dsh05_bad", guard=lambda fn: False)
    assert "dsh05_bad" not in names()          # guard failed -> never surfaced


def test_raw_handler_registered_normally_is_rescued_then_reaches_mcp_guarded():
    """DSH-05 follow-up: register_tool auto-wraps a raw handler, so it DOES reach
    MCP -- but guarded, not raw."""
    import anyio

    import tools.infrastructure.server as server
    from tools.registry import ToolEntry, is_sovereign_wrapper, registry

    raw = ToolEntry(name="dsh05_raw", category="X", description="d",
                    handler=lambda: "hi", is_async=False)
    dispose = registry.register_tool(raw)
    try:
        assert is_sovereign_wrapper(registry.get_tool("dsh05_raw").handler)
        listed = {t.name for t in anyio.run(server.mcp.list_tools)}
        assert "dsh05_raw" in listed
    finally:
        dispose()
        registry.unregister_tool("dsh05_raw")


def test_fastmcp_listener_still_refuses_a_raw_handler_as_belt_and_suspenders():
    """If something ever bypasses register_tool's rescue and fires the listener
    with a raw ToolEntry directly, the MCP boundary still refuses it."""
    import anyio

    import tools.infrastructure.server as server
    from tools.registry import ToolEntry

    raw = ToolEntry(name="dsh05_direct_raw", category="X", description="d",
                    handler=lambda: "unguarded", is_async=False)
    server._register_into_fastmcp(raw)          # bypass register_tool entirely
    listed = {t.name for t in anyio.run(server.mcp.list_tools)}
    assert "dsh05_direct_raw" not in listed
