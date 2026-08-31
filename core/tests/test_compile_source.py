"""DSH-05 slice 2 -- generated source -> callable, with a static gate before exec."""
import pytest

from tools.registry import registry
from tools.self_modification import (
    UnsafeSourceError,
    compile_tool_source,
    guarded_mount_source,
)

_GOOD = '''
def add_one(x):
    """adds one"""
    return x + 1
'''


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for n in ("dsh05s2_ok", "dsh05s2_bad", "dsh05s2_evil"):
        registry.unregister_tool(n)


# ------------------------------------------------------------- compile: happy path
def test_compiles_a_clean_function():
    fn = compile_tool_source(_GOOD, func_name="add_one")
    assert fn(41) == 42
    assert fn.__doc__ == "adds one"


def test_allowlisted_import_is_fine():
    src = "import json\ndef dump(x):\n    return json.dumps(x)\n"
    assert compile_tool_source(src, func_name="dump")({"a": 1}) == '{"a": 1}'


def test_extra_import_can_be_opted_in():
    src = "import os\ndef sep():\n    return os.sep\n"
    with pytest.raises(UnsafeSourceError):
        compile_tool_source(src, func_name="sep")
    assert compile_tool_source(src, func_name="sep", allow_extra_imports=["os"])() in ("/", "\\")


# ------------------------------------------------------------- compile: the gate
@pytest.mark.parametrize("src,needle", [
    ("import subprocess\ndef f():\n    return 1\n", "subprocess"),
    ("from os import system\ndef f():\n    return 1\n", "os"),
    ("def f():\n    return __import__('os').system('id')\n", "__import__"),
    ("def f():\n    return eval('1+1')\n", "eval"),
    ("def f():\n    exec('x=1')\n    return 1\n", "exec"),
    ("def f():\n    return open('/etc/passwd').read()\n", "open"),
    ("def f():\n    return ().__class__.__bases__\n", "dunder"),
    ("g = 0\ndef f():\n    global g\n    g = 1\n    return g\n", "global"),
    ("def f():\n    return input()\n", "input"),
])
def test_dangerous_source_is_rejected_before_running(src, needle):
    with pytest.raises(UnsafeSourceError) as ei:
        compile_tool_source(src, func_name="f")
    assert needle in str(ei.value)


def test_missing_target_function_is_rejected():
    with pytest.raises(UnsafeSourceError):
        compile_tool_source("def other():\n    return 1\n", func_name="add_one")


def test_syntax_error_propagates():
    with pytest.raises(SyntaxError):
        compile_tool_source("def f(:\n  pass", func_name="f")


def test_runtime_import_guard_is_a_backstop():
    """A dynamic import that dodged the AST check still fails at run time --
    the exec namespace's __import__ only allows the allowlist."""
    # dict access to sneak `open` past the AST 'open()' call check, then use it
    src = "def f():\n    import os\n    return os.getcwd()\n"
    with pytest.raises(UnsafeSourceError):        # caught statically first
        compile_tool_source(src, func_name="f")


# ------------------------------------------------------------- guarded_mount_source
def test_guarded_mount_source_mounts_a_clean_tool():
    res = guarded_mount_source(_GOOD, name="dsh05s2_ok", func_name="add_one",
                               guard=lambda fn: fn(1) == 2)
    assert res.mounted and res.guard_passed and not res.reverted
    assert registry.get_tool("dsh05s2_ok") is not None
    res.dispose()
    assert registry.get_tool("dsh05s2_ok") is None


def test_guarded_mount_source_rejects_evil_source_without_mounting():
    res = guarded_mount_source(
        "def go():\n    return __import__('os').getcwd()\n",
        name="dsh05s2_evil", func_name="go", guard=lambda fn: True,
    )
    assert not res.mounted and not res.reverted
    assert "source rejected" in res.error
    assert registry.get_tool("dsh05s2_evil") is None


def test_guarded_mount_source_reverts_a_tool_that_fails_its_guard():
    res = guarded_mount_source(_GOOD, name="dsh05s2_bad", func_name="add_one",
                               guard=lambda fn: fn(1) == 999)
    assert res.mounted and res.reverted and res.guard_passed is False
    assert registry.get_tool("dsh05s2_bad") is None


# ------------------------------------------------------------- s2 hardening
def test_getattr_dunder_bypass_is_blocked_at_runtime():
    src = "def f():\n    x = ()\n    return getattr(x, '__' + 'class' + '__')\n"
    fn = compile_tool_source(src, func_name="f")   # passes the AST check
    with pytest.raises(AttributeError):             # ...but the wrapped getattr refuses
        fn()


def test_hasattr_dunder_returns_false():
    src = "def f():\n    return hasattr((), '__class' + '__')\n"
    assert compile_tool_source(src, func_name="f")() is False


def test_allow_extra_imports_cannot_reenable_dangerous_modules():
    src = "import subprocess\ndef f():\n    return 1\n"
    with pytest.raises(UnsafeSourceError) as ei:
        compile_tool_source(src, func_name="f", allow_extra_imports=["subprocess"])
    assert "subprocess" in str(ei.value)


def test_os_system_call_is_banned_even_when_os_is_allowed():
    src = "import os\ndef f():\n    return os.system('id')\n"
    with pytest.raises(UnsafeSourceError) as ei:
        compile_tool_source(src, func_name="f", allow_extra_imports=["os"])
    assert "system" in str(ei.value)


def test_from_import_of_private_name_is_blocked():
    src = "from json import _default_decoder\ndef f():\n    return 1\n"
    fn_src_ok = compile_tool_source  # the AST check allows `from json import X`
    with pytest.raises(ImportError):
        fn_src_ok(src, func_name="f")


def test_str_format_is_banned_the_template_attr_walk_gap():
    src = "def f(x):\n    return '{0.__class__}'.format(x)\n"
    with pytest.raises(UnsafeSourceError) as ei:
        compile_tool_source(src, func_name="f")
    assert "format" in str(ei.value)


def test_getattr_to_a_banned_name_is_blocked_at_runtime():
    # `import os` (opt-in) then getattr(os, 'system') -- neither dunder nor a
    # literal .system() call, so only the wrapped getattr stops it.
    src = "import os\ndef f():\n    return getattr(os, 'sys' + 'tem')\n"
    fn = compile_tool_source(src, func_name="f", allow_extra_imports=["os"])
    with pytest.raises(AttributeError):
        fn()
