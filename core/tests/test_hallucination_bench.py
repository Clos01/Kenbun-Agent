"""Unit tests for the pure scorer in core/benchmarks/hallucination_bench.py.

No live model required — these lock in the violation detectors so prompt
tweaks and model swaps can be compared on a stable rubric.
"""
import json

from core.benchmarks.hallucination_bench import (
    CASES,
    PROMPT_SET_VERSION,
    normalize_gateway_result,
    score_response,
)


def _tc(name, **args):
    return {"function": {"name": name, "arguments": json.dumps(args)}}


def _case(**overrides):
    base = {"id": "t", "category": "few_shot_alignment", "prompt": "x", "expect_tool": None}
    base.update(overrides)
    return base


def test_clean_native_tool_call_passes():
    score = score_response("", [_tc("execute_shell", command="ls -la")], _case(expect_tool="execute_shell"))
    assert score["violations"] == []
    assert score["tool_compliant"] is True


def test_kenbun_wrap_in_command_detected():
    score = score_response("", [_tc("execute_shell", command="kenbun search_hivemind_concepts query=docker")], _case())
    assert any(v["type"] == "kenbun_wrap" for v in score["violations"])


def test_kenbun_wrap_in_code_block_detected():
    content = "Run this:\n```bash\nkenbun scan_repo\n```"
    score = score_response(content, [], _case())
    assert any(v["type"] == "kenbun_wrap" for v in score["violations"])


def test_plain_mention_of_kenbun_is_not_a_violation():
    # Talking ABOUT kenbun in prose is fine; only command-position usage counts
    score = score_response("Kenbun is an agent framework with a hivemind memory.", [], _case())
    assert score["violations"] == []


def test_xml_leak_detected():
    for leak in ["<tool_call>{...}</tool_call>", "<function_call name='x'>", "[TOOL_CALL] execute_shell"]:
        score = score_response(f"Sure! {leak}", [], _case())
        assert any(v["type"] == "xml_leak" for v in score["violations"]), leak


def test_malformed_arguments_detected():
    bad = {"function": {"name": "execute_shell", "arguments": "{command: ls}"}}
    score = score_response("", [bad], _case())
    assert any(v["type"] == "malformed_arguments" for v in score["violations"])


def test_unknown_tool_detected():
    score = score_response("", [_tc("run_kenbun_tool", tool="scan_repo")], _case())
    assert any(v["type"] == "unknown_tool" for v in score["violations"])


def test_missing_required_argument_detected():
    score = score_response("", [_tc("execute_shell", cmd="ls")], _case())
    assert any(v["type"] == "missing_argument" for v in score["violations"])


def test_expected_tool_missing_is_noncompliant_not_hallucination():
    score = score_response("You should run ls yourself.", [], _case(expect_tool="execute_shell"))
    assert score["violations"] == []
    assert score["tool_compliant"] is False


def test_forbidden_tool_use_is_noncompliant():
    score = score_response("", [_tc("execute_shell", command="ls")], _case(forbid_tool=True))
    assert score["tool_compliant"] is False


def test_normalize_gateway_result_shapes():
    assert normalize_gateway_result("hi") == ("hi", [])
    assert normalize_gateway_result(None) == ("", [])
    content, calls = normalize_gateway_result({"content": "ok", "tool_calls": [_tc("execute_shell", command="ls")]})
    assert content == "ok" and len(calls) == 1


def test_prompt_set_is_stable_and_well_formed():
    # The rubric only means something if the prompt set stays fixed per version
    assert PROMPT_SET_VERSION == "1.0"
    assert len(CASES) == 12
    assert len({c["id"] for c in CASES}) == 12
    categories = {c["category"] for c in CASES}
    assert categories == {"few_shot_alignment", "tool_synthesis", "schema_strictness", "negative_constraint"}
