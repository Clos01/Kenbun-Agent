"""DSH-01 — registration is a revertible effect.

A tool (or pipeline) can be registered and then fully retracted at runtime: the
disposer removes exactly what it added, is safe to call twice, does not evict a
later re-registration under the same name, and notifies mirrors (FastMCP) so they
tear their copy down too. No process restart.
"""
import threading

import anyio
import pytest

from tools.registry import SovereignRegistry, ToolEntry, PipelineEntry


def _tool(name: str = "t") -> ToolEntry:
    return ToolEntry(name=name, category="Test", description="d",
                     handler=lambda: None, is_async=False)


def _pipeline(name: str = "p") -> PipelineEntry:
    return PipelineEntry(name=name, description="d", builder=lambda: None)


# --------------------------------------------------------------------- disposer
def test_disposer_removes_exactly_what_it_added():
    r = SovereignRegistry()
    dispose = r.register_tool(_tool("alpha"))
    assert r.get_tool("alpha") is not None
    dispose()
    assert r.get_tool("alpha") is None
    assert "alpha" not in r.get_all_tools()


def test_disposer_is_idempotent():
    r = SovereignRegistry()
    dispose = r.register_tool(_tool("alpha"))
    dispose()
    dispose()  # must not raise
    assert r.get_tool("alpha") is None


def test_disposer_does_not_clobber_reregistration():
    r = SovereignRegistry()
    first = _tool("alpha")
    dispose_first = r.register_tool(first)
    second = _tool("alpha")
    r.register_tool(second)          # replaces `first` under the same name
    dispose_first()                  # stale handle
    assert r.get_tool("alpha") is second


def test_pipeline_disposer_symmetry():
    r = SovereignRegistry()
    dispose = r.register_pipeline(_pipeline("p1"))
    assert r.get_pipeline("p1") is not None
    dispose()
    assert r.get_pipeline("p1") is None


# -------------------------------------------------------------------- listeners
def test_removal_listener_fires_once_with_the_name():
    r = SovereignRegistry()
    seen: list[str] = []
    r.add_removal_listener(seen.append)
    dispose = r.register_tool(_tool("alpha"))
    dispose()
    dispose()
    assert seen == ["alpha"]


def test_unregister_tool_returns_bool_and_notifies():
    r = SovereignRegistry()
    seen: list[str] = []
    r.add_removal_listener(seen.append)
    r.register_tool(_tool("alpha"))
    assert r.unregister_tool("alpha") is True
    assert r.unregister_tool("alpha") is False
    assert seen == ["alpha"]


def test_a_raising_listener_does_not_block_removal_or_other_listeners():
    r = SovereignRegistry()
    calls: list[str] = []

    def boom(_name: str) -> None:
        raise RuntimeError("mirror is on fire")

    r.add_removal_listener(boom)
    r.add_removal_listener(calls.append)
    dispose = r.register_tool(_tool("alpha"))
    dispose()
    assert calls == ["alpha"]
    assert r.get_tool("alpha") is None


def test_removal_listener_can_be_detached():
    r = SovereignRegistry()
    seen: list[str] = []
    detach = r.add_removal_listener(seen.append)
    r.register_tool(_tool("a"))
    r.unregister_tool("a")
    detach()
    r.register_tool(_tool("b"))
    r.unregister_tool("b")
    assert seen == ["a"]


def test_listener_observes_the_post_removal_state():
    """Notify fires under the same lock hold as the delete: by the time a listener
    runs, the entry is already gone and nothing could have interleaved."""
    r = SovereignRegistry()
    observed = {}

    def check(name: str) -> None:
        observed["present_at_notify"] = r.get_tool(name) is not None

    r.add_removal_listener(check)
    dispose = r.register_tool(_tool("alpha"))
    dispose()
    assert observed["present_at_notify"] is False


def test_concurrent_register_and_dispose_stays_consistent():
    """Each worker registers a uniquely-named tool then disposes it. The mirror
    (a listener) and the registry must agree at the end: every tool gone, every
    removal seen exactly once, no spurious events."""
    r = SovereignRegistry()
    removed: list[str] = []
    lock = threading.Lock()

    def mirror(name: str) -> None:
        with lock:
            removed.append(name)

    r.add_removal_listener(mirror)

    def worker(i: int) -> None:
        name = f"tool_{i}"
        dispose = r.register_tool(_tool(name))
        dispose()
        dispose()  # idempotent under contention

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert r.get_all_tools() == {}
    assert sorted(removed) == sorted(f"tool_{i}" for i in range(50))


def test_exclusive_register_rejects_a_duplicate_name_atomically():
    r = SovereignRegistry()
    first = _tool("alpha")
    r.register_tool(first)
    with pytest.raises(KeyError):
        r.register_tool(_tool("alpha"), exclusive=True)
    assert r.get_tool("alpha") is first          # original untouched
    # non-exclusive still overwrites (the decorator's import-time behaviour)
    second = _tool("alpha")
    r.register_tool(second)
    assert r.get_tool("alpha") is second


def test_registration_listener_fires_with_the_entry():
    r = SovereignRegistry()
    seen: list = []
    detach = r.add_registration_listener(seen.append)
    e = _tool("alpha")
    r.register_tool(e)
    assert seen == [e]
    detach()
    r.register_tool(_tool("beta"))
    assert seen == [e]                       # detached, no beta


def test_a_raising_registration_listener_does_not_block_registration():
    r = SovereignRegistry()
    r.add_registration_listener(lambda e: (_ for _ in ()).throw(RuntimeError("mirror down")))
    got: list = []
    r.add_registration_listener(got.append)
    e = _tool("alpha")
    r.register_tool(e)
    assert r.get_tool("alpha") is e
    assert got == [e]


def test_clear_notifies_for_every_removed_entry():
    r = SovereignRegistry()
    tools_seen: list[str] = []
    pipes_seen: list[str] = []
    r.add_removal_listener(tools_seen.append)
    r.add_pipeline_removal_listener(pipes_seen.append)
    r.register_tool(_tool("a"))
    r.register_tool(_tool("b"))
    r.register_pipeline(_pipeline("p"))
    r.clear()
    assert sorted(tools_seen) == ["a", "b"]
    assert pipes_seen == ["p"]


# ------------------------------------------------------------------- decorator
def test_sovereign_tool_decorator_exposes_a_working_disposer():
    from tools.registry import registry, sovereign_tool

    @sovereign_tool(name="dsh01_decorator_probe", category="Test")
    def dsh01_decorator_probe():
        """probe"""
        return "ok"

    try:
        assert registry.get_tool("dsh01_decorator_probe") is not None
        assert dsh01_decorator_probe._sovereign_tool_name == "dsh01_decorator_probe"
        dsh01_decorator_probe._sovereign_disposer()
        assert registry.get_tool("dsh01_decorator_probe") is None
    finally:
        registry.unregister_tool("dsh01_decorator_probe")


# ------------------------------------------------------- end-to-end: FastMCP mirror
def test_registry_removal_tears_down_the_fastmcp_mirror():
    """The slice-1 promise: register -> in the MCP tool list -> dispose -> gone.

    Replicates server.py's ~6-line mirror wiring against a throwaway FastMCP so
    the real (import-heavy) server module is not needed.
    """
    from mcp.server.fastmcp import FastMCP

    r = SovereignRegistry()
    mcp = FastMCP("dsh01-test")
    clean_names: dict[str, str] = {}

    def mirror_remove(registry_name: str) -> None:
        clean = clean_names.pop(registry_name, None)
        if clean is None:
            return
        try:
            mcp.remove_tool(clean)
        except Exception:
            pass

    r.add_removal_listener(mirror_remove)

    entry = _tool("live_tool")
    dispose = r.register_tool(entry)
    mcp.add_tool(entry.handler, name=entry.name, description=entry.description)
    clean_names[entry.name] = entry.name

    listed = [t.name for t in anyio.run(mcp.list_tools)]
    assert "live_tool" in listed

    dispose()

    listed_after = [t.name for t in anyio.run(mcp.list_tools)]
    assert "live_tool" not in listed_after
