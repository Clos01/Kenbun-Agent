"""Spec generation: parsing, the endpoint ladder, and escalation.

These cover the failure that made generate_wireframe() unusable: the spec call
was routed at a local completion-style model that answers a JSON request with
prose. Its reply was non-empty, so the router counted it a success and the
3-attempt loop retried the same incapable endpoint until it gave up.

The invariants worth pinning are therefore about ROUTING, not about wording:
a non-JSON answer must advance to the next model rather than be retried in
place, and a rung must not be able to report success by quietly answering from
somewhere else.
"""
import json

import pytest

from tools.craft import wireframe_graph as wg


GOOD_SPEC = {
    "title": "Task Tracker",
    "screens": [{"name": "Login", "components": [{"type": "button", "label": "Sign in"}]}],
    "backend": {"entities": [], "endpoints": [], "flows": [], "integrations": []},
}

# The verbatim shape of the real failure: the local model continues the user's
# sentence instead of answering it.
COMPLETION_GARBAGE = (
    "\nI am looking for a simple task tracker that allows me to:\n"
    "  1. Create a list of tasks (e.g., “Buy milk”)\n"
)


# --- _parse_spec ---------------------------------------------------------

def test_parse_spec_accepts_bare_json():
    assert wg._parse_spec(json.dumps(GOOD_SPEC))["title"] == "Task Tracker"


def test_parse_spec_strips_markdown_fence():
    assert wg._parse_spec("```json\n" + json.dumps(GOOD_SPEC) + "\n```") is not None


def test_parse_spec_recovers_json_embedded_in_prose():
    raw = "Sure! Here is the spec:\n" + json.dumps(GOOD_SPEC) + "\nHope that helps."
    assert wg._parse_spec(raw) is not None


def test_parse_spec_rejects_completion_garbage():
    assert wg._parse_spec(COMPLETION_GARBAGE) is None


def test_parse_spec_rejects_malformed_json():
    assert wg._parse_spec('{"screens": [ }') is None


@pytest.mark.parametrize("payload", ['{}', '{"title": "x"}', '{"screens": []}', '[1, 2]'])
def test_parse_spec_rejects_json_that_is_not_a_spec(payload):
    """A screenless object is a failed attempt, not a successful one.

    Accepting it would let the ladder stop on garbage and blow up later inside
    spec_to_graph, far from the endpoint that actually caused it.
    """
    assert wg._parse_spec(payload) is None


# --- the ladder ----------------------------------------------------------

def test_ladder_ends_with_the_default_gateway():
    """The last rung must stay (None, None) so a host with no cloud key still works."""
    assert wg._spec_endpoints()[-1][:2] == (None, None)


def test_ladder_names_a_model_for_every_rung_but_the_last():
    for url, model, label in wg._spec_endpoints()[:-1]:
        assert url and model, f"rung {label} must name its endpoint and model"


def test_ladder_skips_cloud_rungs_when_unconfigured(monkeypatch):
    from tools.infrastructure import config
    monkeypatch.setattr(config.settings, "AUDIT_LLM_URL", "", raising=False)
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", None, raising=False)
    monkeypatch.setattr(config.settings, "DESIGN_LLM_URL", "", raising=False)
    assert wg._spec_endpoints() == [(None, None, "default gateway")]


def test_design_rung_is_configurable_not_hardcoded(monkeypatch):
    """The model must be movable from config, without editing this module."""
    from tools.infrastructure import config
    monkeypatch.setattr(config.settings, "DESIGN_LLM_URL", "http://elsewhere", raising=False)
    monkeypatch.setattr(config.settings, "DESIGN_LLM_MODEL", "some-model", raising=False)
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "k", raising=False)
    assert ("http://elsewhere", "some-model", "design/cloud") in wg._spec_endpoints()


def test_ladder_ignores_an_empty_secretstr_anthropic_key(monkeypatch):
    """SecretStr("") is a truthy object; testing the wrapper would enable a dead rung."""
    from pydantic import SecretStr
    from tools.infrastructure import config
    monkeypatch.setattr(config.settings, "ANTHROPIC_API_KEY", SecretStr(""), raising=False)
    assert not any(label == "audit/cloud" for _, _, label in wg._spec_endpoints())


# --- escalation ----------------------------------------------------------

@pytest.fixture
def two_rung_ladder(monkeypatch):
    monkeypatch.setattr(wg, "_spec_endpoints", lambda: [
        ("http://weak", "weak-model", "weak"),
        (None, None, "default gateway"),
    ])


def test_non_json_answer_escalates_to_the_next_rung(two_rung_ladder, monkeypatch):
    """The core regression: prose from rung 1 must not trap the loop on rung 1."""
    calls = []

    def fake(url, model, sysprompt, msg):
        calls.append(model)
        return COMPLETION_GARBAGE if model == "weak-model" else json.dumps(GOOD_SPEC)

    monkeypatch.setattr(wg, "_call_rung", fake)
    assert wg.generate_spec("a task tracker")["title"] == "Task Tracker"
    assert calls[-1] is None, "must have reached the second rung"
    assert calls.count("weak-model") <= 2, "must not burn every attempt on one endpoint"


def test_a_raising_rung_advances_immediately(two_rung_ladder, monkeypatch):
    calls = []

    def fake(url, model, sysprompt, msg):
        calls.append(model)
        if model == "weak-model":
            raise RuntimeError("401 Unauthorized")
        return json.dumps(GOOD_SPEC)

    monkeypatch.setattr(wg, "_call_rung", fake)
    assert wg.generate_spec("a task tracker") is not None
    assert calls == ["weak-model", None], "a dead rung should not be retried in place"


def test_retry_feeds_back_the_rejected_output(two_rung_ladder, monkeypatch):
    """Attempt 2 must differ from attempt 1, or a deterministic endpoint just repeats itself."""
    seen = []

    def fake(url, model, sysprompt, msg):
        seen.append(msg)
        return json.dumps(GOOD_SPEC) if len(seen) > 1 else "not json"

    monkeypatch.setattr(wg, "_call_rung", fake)
    wg.generate_spec("a task tracker")
    assert len(seen) == 2
    assert seen[0] != seen[1]
    assert "not json" in seen[1], "the rejected output must be shown back to the model"


def test_first_rung_wins_without_touching_the_rest(two_rung_ladder, monkeypatch):
    calls = []
    monkeypatch.setattr(wg, "_call_rung", lambda url, model, s, m: (
        calls.append(model) or json.dumps(GOOD_SPEC)))
    wg.generate_spec("a task tracker")
    assert calls == ["weak-model"]


def test_total_failure_names_every_endpoint_it_tried(two_rung_ladder, monkeypatch):
    """An anonymous 'failed after 3 attempts' is what made this bug undiagnosable."""
    monkeypatch.setattr(wg, "_call_rung", lambda url, model, s, m: COMPLETION_GARBAGE)
    with pytest.raises(ValueError) as exc:
        wg.generate_spec("a task tracker")
    assert "weak-model" in str(exc.value)
    assert "default gateway" in str(exc.value)


def test_amendment_mode_carries_the_prior_spec(two_rung_ladder, monkeypatch):
    seen = []
    monkeypatch.setattr(wg, "_call_rung", lambda url, model, s, m: (
        seen.append((s, m)) or json.dumps(GOOD_SPEC)))
    wg.generate_spec("fix the login screen", prior_spec=GOOD_SPEC)
    sysprompt, user_msg = seen[0]
    assert "AMENDMENT MODE" in sysprompt
    assert "Task Tracker" in user_msg


def test_named_rungs_do_not_route_through_the_silently_substituting_gateway(monkeypatch):
    """call_llm_gateway answers from a different model when the requested one fails.

    A named rung must go straight at its endpoint, otherwise a 401 comes back as a
    200 from the cost bandit's cheapest arm and escalation can never happen.
    """
    monkeypatch.setattr(
        "tools.utils.llm_router.call_llm_gateway",
        lambda *a, **k: pytest.fail("named rung must not use the fallback gateway"),
    )
    monkeypatch.setattr(
        "tools.utils.llm_router._make_openai_compatible_call",
        lambda url, model, *a, **k: json.dumps({"ok": url, "model": model}),
    )
    out = json.loads(wg._call_rung("http://pinned", "pinned-model", "sys", "msg"))
    assert out == {"ok": "http://pinned", "model": "pinned-model"}


def test_the_last_rung_does_use_the_gateway(monkeypatch):
    """By then there is nothing to escalate to, so the router's own chain is the net."""
    monkeypatch.setattr(
        "tools.utils.llm_router.call_llm_gateway", lambda *a, **k: "gateway-answer")
    assert wg._call_rung(None, None, "sys", "msg") == "gateway-answer"


# --- flow -> endpoint join ----------------------------------------------

def _graph_with_task_collection(flow_to):
    """A CRUD collection: one path, two methods — the shape that exposed the join bug."""
    return wg.spec_to_graph({
        "title": "T",
        "screens": [{
            "name": "Create Task",
            "components": [{"type": "button", "label": "Save Task"}],
        }],
        "backend": {
            "endpoints": [
                {"method": "GET", "path": "/api/tasks"},
                {"method": "POST", "path": "/api/tasks"},
            ],
            "flows": [{"from": "Save Task", "to": flow_to}],
        },
    })


def _flow_target(doc):
    edge = next(e for e in doc["edges"] if e["kind"] == "flow")
    return next(n for n in doc["nodes"] if n["id"] == edge["target"])["label"]


def test_bare_path_flow_resolves_to_the_writing_endpoint():
    """The schema asks for a bare path, so "/api/tasks" must not land on the GET."""
    assert _flow_target(_graph_with_task_collection("/api/tasks")) == "POST /api/tasks"


def test_an_explicit_method_in_the_flow_is_obeyed():
    """prefer_write must not override a target the spec actually spelled out."""
    assert _flow_target(_graph_with_task_collection("GET /api/tasks")) == "GET /api/tasks"


def test_a_read_only_path_still_resolves():
    doc = wg.spec_to_graph({
        "title": "T",
        "screens": [{"name": "S", "components": [{"type": "button", "label": "Refresh"}]}],
        "backend": {
            "endpoints": [{"method": "GET", "path": "/api/tasks"}],
            "flows": [{"from": "Refresh", "to": "/api/tasks"}],
        },
    })
    assert _flow_target(doc) == "GET /api/tasks"


def test_an_unknown_endpoint_is_reported_not_silently_dropped():
    doc = wg.spec_to_graph({
        "title": "T",
        "screens": [{"name": "S", "components": [{"type": "button", "label": "Go"}]}],
        "backend": {
            "endpoints": [{"method": "GET", "path": "/api/tasks"}],
            "flows": [{"from": "Go", "to": "/api/nope"}],
        },
    })
    assert not [e for e in doc["edges"] if e["kind"] == "flow"]
    assert doc.get("warnings"), "an unjoinable flow must surface, not vanish"


def test_integration_via_a_shared_path_still_connects():
    doc = wg.spec_to_graph({
        "title": "T",
        "screens": [],
        "backend": {
            "endpoints": [
                {"method": "GET", "path": "/api/tasks"},
                {"method": "POST", "path": "/api/tasks"},
            ],
            "integrations": [{"name": "SendGrid", "kind": "email", "via": ["/api/tasks"]}],
        },
    }, detail="contracts")  # integrations only render at the contracts level
    assert [e for e in doc["edges"] if e["kind"] == "integration"]
