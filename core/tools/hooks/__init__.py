"""Command-hook wire protocol (DSH-05, hooks half).

A Python port of DeepSeek-Harness's ``hook-protocol``: one shared vocabulary for
shell hooks fired at lifecycle points (``PreToolUse``, ``UserPromptSubmit``,
``Stop``, ...). ``protocol`` is the codec + matcher + runner for a single hook;
``registry`` loads a ``hooks.json`` and fires every matching hook at a point,
folding the outcomes into one :class:`FiredResult`.

Hook commands are trusted operator config (like a git hook), not model input --
they run with ``shell=True`` and are NOT subject to the model-command allowlist,
but the child env has parent-process secrets scrubbed.
"""
from .protocol import (
    CommandHook,
    HookOutput,
    MatcherGroup,
    matcher_diagnostic,
    matches_matcher,
    parse_hook_output,
    run_hook,
)
from .registry import FiredResult, HookRegistry, default_registry

__all__ = [
    "CommandHook",
    "MatcherGroup",
    "HookOutput",
    "matches_matcher",
    "matcher_diagnostic",
    "parse_hook_output",
    "run_hook",
    "HookRegistry",
    "FiredResult",
    "default_registry",
]
