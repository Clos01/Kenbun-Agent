"""DSH-05 slice 2 -- turn generated Python *source* into a callable, carefully.

``hot_mount.py`` (slice 1) mounts an *already-defined* callable and deliberately
never ``exec``s anything. This module is the missing step for
``agent_self_improve``: it takes source text produced by Kenbun's own generation
pipeline and returns a callable, with two gates in front of the ``exec``:

1. **AST allowlist** -- the source is parsed and rejected *before it runs* if it
   imports anything outside ``_ALLOWED_IMPORTS``, calls ``eval`` / ``exec`` /
   ``compile`` / ``__import__`` / ``open`` / ``input`` / ``globals`` / ..., reads
   or writes a dunder attribute, or uses ``global`` / ``nonlocal``.
2. **Restricted exec** -- the code runs with a curated ``__builtins__`` (no
   ``open``, ``exec``, ``eval``, ``__import__``, ``compile``, ``input``) and an
   empty module namespace; only allowlisted modules can be imported.

This is defence in depth, **not a hardened sandbox**. Known residual gaps: a
``"{0.__class__}".format(x)`` template string hides the attribute walk from the
AST pass (``str.format`` resolves it at run time). ``getattr`` / ``hasattr`` are
handled -- the run-time versions reject dunder names, including
``getattr(x, '__' + 'class' + '__')``. The trust assumption from slice 1 stands:
the source comes from Kenbun's prompt/tool generator, never from a tool argument
or routed model/user input; for untrusted source use a subprocess / container.
What the two gates *do* buy: a hallucinated ``import subprocess``, ``open(...)``,
or ``os.system(...)`` from the generator is rejected before it runs, with a
clear reason, instead of silently executing.
"""
from __future__ import annotations

import ast
import logging
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional

logger = logging.getLogger("kenbun.self_modification")


class UnsafeSourceError(ValueError):
    """The generated source failed a static-safety check and was not executed."""


# Modules a generated tool may import. Keep this tight -- add on evidence, not
# on spec. Submodule access ("os.path") is allowed only if the top name is here.
_ALLOWED_IMPORTS: FrozenSet[str] = frozenset({
    "json", "re", "math", "statistics", "datetime", "time", "typing",
    "dataclasses", "collections", "itertools", "functools", "textwrap",
    "string", "uuid", "hashlib", "base64", "enum",
})

# Modules that ``allow_extra_imports`` can NEVER re-enable -- process / FS /
# native-code reach, and the reflection escape hatches.
_NEVER_IMPORT: FrozenSet[str] = frozenset({
    "subprocess", "sys", "socket", "ctypes", "importlib", "builtins", "pickle",
    "marshal", "multiprocessing", "pty", "signal", "shutil", "pathlib",
    "resource", "gc", "inspect", "code", "codeop", "runpy",
})

# Names that must never be *called* from generated source. Includes attribute
# names (``os.system(...)`` -> ``func.attr == "system"``). ``format`` /
# ``format_map`` are here because a template string ("{0.__class__}".format(x))
# hides an attribute walk from the AST -- generated tool code uses f-strings
# (which the auditor *can* see) or ``+`` instead.
_BANNED_CALLS: FrozenSet[str] = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "vars", "breakpoint", "help", "exit", "quit",
    "setattr", "delattr", "memoryview", "format", "format_map",
    "system", "popen", "fork", "forkpty", "execv", "execve", "execvp",
    "spawnv", "spawnl", "spawnlp", "kill", "killpg",
})

# The builtins a generated tool is allowed to see at run time. `getattr` /
# `hasattr` are NOT here -- they're injected as wrapped versions that reject
# dunder attribute names, so `getattr(x, '__' + 'class' + '__')` fails at run
# time too (the AST check only sees literal `x.__class__`).
_SAFE_BUILTINS: FrozenSet[str] = frozenset({
    "abs", "all", "any", "bool", "bytes", "bytearray", "callable", "chr",
    "dict", "divmod", "enumerate", "filter", "float", "format", "frozenset",
    "hash", "hex", "int", "isinstance", "issubclass",
    "iter", "len", "list", "map", "max", "min", "next", "object", "oct", "ord",
    "pow", "print", "range", "repr", "reversed", "round", "set", "slice",
    "sorted", "str", "sum", "tuple", "type", "zip", "True", "False", "None",
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "RuntimeError", "StopIteration", "ZeroDivisionError", "AttributeError",
    "NotImplementedError", "__build_class__",   # needed for `class` bodies
})


class _Auditor(ast.NodeVisitor):
    def __init__(self, allowed_imports: FrozenSet[str]) -> None:
        self._allowed = allowed_imports
        self.problems: List[str] = []

    def _fail(self, node: ast.AST, msg: str) -> None:
        self.problems.append(f"line {getattr(node, 'lineno', '?')}: {msg}")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.split(".")[0] not in self._allowed:
                self._fail(node, f"import of {alias.name!r} is not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            self._fail(node, "relative imports are not allowed")
        else:
            top = (node.module or "").split(".")[0]
            if not top or top not in self._allowed:
                self._fail(node, f"import from {node.module!r} is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in _BANNED_CALLS:
            self._fail(node, f"call to {func.id!r} is not allowed")
        if isinstance(func, ast.Attribute) and func.attr in _BANNED_CALLS:
            self._fail(node, f"call to .{func.attr}() is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self._fail(node, f"dunder attribute access {node.attr!r} is not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__") and node.id.endswith("__") and node.id != "__name__":
            self._fail(node, f"dunder name {node.id!r} is not allowed")
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self._fail(node, "`global` is not allowed")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self._fail(node, "`nonlocal` is not allowed")


def _dunder(name: object) -> bool:
    return isinstance(name, str) and name.startswith("__") and name.endswith("__")


def _guarded_import(allowed: FrozenSet[str]) -> Callable[..., Any]:
    """A drop-in ``__import__`` that only lets allowlisted top-level modules
    through, and never a ``_``-prefixed name in ``fromlist`` -- a runtime
    backstop behind the AST check."""
    import builtins

    real_import = builtins.__import__

    def _imp(name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0 or name.split(".")[0] not in allowed:
            raise ImportError(f"import of {name!r} is blocked in hot-mount source")
        if fromlist and any(isinstance(n, str) and n.startswith("_") for n in fromlist):
            raise ImportError(f"importing a private name from {name!r} is blocked")
        return real_import(name, globals, locals, fromlist, level)

    return _imp


def _restricted_builtins(allowed_imports: FrozenSet[str]) -> Dict[str, Any]:
    import builtins

    b: Dict[str, Any] = {n: getattr(builtins, n) for n in _SAFE_BUILTINS if hasattr(builtins, n)}
    b["__import__"] = _guarded_import(allowed_imports)

    _real_getattr = builtins.getattr

    def _safe_getattr(obj, name, *default):
        if _dunder(name) or name in _BANNED_CALLS:
            raise AttributeError(f"getattr() to {name!r} is blocked in hot-mount source")
        return _real_getattr(obj, name, *default)

    def _safe_hasattr(obj, name):
        if _dunder(name) or name in _BANNED_CALLS:
            return False
        return hasattr(obj, name)

    b["getattr"] = _safe_getattr
    b["hasattr"] = _safe_hasattr
    return b


def compile_tool_source(
    source: str,
    *,
    func_name: str,
    allow_extra_imports: Optional[Iterable[str]] = None,
) -> Callable:
    """Statically vet ``source`` and, if it passes, exec it in a restricted
    namespace and return the top-level function named ``func_name``.

    Raises :class:`UnsafeSourceError` (before running anything) on a failed
    check, :class:`SyntaxError` if the source does not parse, or ``TypeError``
    if ``func_name`` is missing / not callable.
    """
    extra = frozenset(allow_extra_imports or ())
    forbidden = extra & _NEVER_IMPORT
    if forbidden:
        raise UnsafeSourceError(
            f"allow_extra_imports may not re-enable {sorted(forbidden)}"
        )
    allowed = _ALLOWED_IMPORTS | extra

    tree = ast.parse(source, filename="<hot_mount source>", mode="exec")

    auditor = _Auditor(allowed)
    auditor.visit(tree)
    if auditor.problems:
        raise UnsafeSourceError("; ".join(auditor.problems[:8]))

    top_funcs = [n.name for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if func_name not in top_funcs:
        raise UnsafeSourceError(
            f"source defines no top-level function {func_name!r} (found: {top_funcs or 'none'})"
        )

    ns: dict = {"__builtins__": _restricted_builtins(allowed), "__name__": "<hot_mount>"}
    code = compile(tree, "<hot_mount source>", "exec")
    exec(code, ns)  # noqa: S102 -- gated by the auditor + restricted builtins above

    fn = ns.get(func_name)
    if not callable(fn):
        raise TypeError(f"{func_name!r} did not resolve to a callable")
    logger.debug("compile_tool_source: %r compiled (%d chars)", func_name, len(source))
    return fn
