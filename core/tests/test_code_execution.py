import os
import sys
import json
import time
import pytest
from unittest.mock import patch, MagicMock
from tools.execution.execute_code_tool import execute_code
from tools.registry import sovereign_tool, registry
from tools.infrastructure.config import settings

@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure dummy test tools are cleaned up after each test."""
    yield
    registry._tools.pop("dummy_test_tool", None)
    registry._tools.pop("dummy_failing_tool", None)

def test_execute_code_basic_success():
    """Verifies that simple Python code executes successfully and returns stdout."""
    code = """
import sys
print("Hello from child")
sys.exit(0)
"""
    result_str = execute_code(code, mode="strict")
    result = json.loads(result_str)
    
    assert result["status"] == "success"
    assert result["exit_code"] == 0
    assert "Hello from child" in result["stdout"]
    assert result["stderr"] == ""
    assert result["tool_calls_made"] == 0

def test_execute_code_syntax_error():
    """Verifies that invalid Python code returns an error status and stderr traceback."""
    code = """
this is not valid python code
"""
    result_str = execute_code(code, mode="strict")
    result = json.loads(result_str)
    
    assert result["status"] == "error"
    assert result["exit_code"] != 0
    assert "SyntaxError" in result["stderr"]

def test_execute_code_env_scrubbing():
    """Verifies that environment variables containing sensitive keywords are scrubbed."""
    os.environ["TEST_SECRET_KEY"] = "super-secret-value"
    os.environ["API_TOKEN_XYZ"] = "token-value"
    os.environ["SAFE_ENV_VAR"] = "safe-value"
    
    code = """
import os
import json
print(json.dumps({
    "has_secret": "TEST_SECRET_KEY" in os.environ,
    "has_token": "API_TOKEN_XYZ" in os.environ,
    "safe_val": os.environ.get("SAFE_ENV_VAR")
}))
"""
    try:
        result_str = execute_code(code, mode="strict")
        result = json.loads(result_str)
        assert result["status"] == "success"
        
        child_env = json.loads(result["stdout"].strip())
        assert child_env["has_secret"] is False
        assert child_env["has_token"] is False
        assert child_env["safe_val"] == "safe-value"
    finally:
        os.environ.pop("TEST_SECRET_KEY", None)
        os.environ.pop("API_TOKEN_XYZ", None)
        os.environ.pop("SAFE_ENV_VAR", None)

def test_execute_code_stdout_stderr_capping():
    """Verifies that stdout and stderr outputs are capped within limits."""
    # Print more than 50KB to trigger stdout truncation
    # Large block of characters (60,000 'A's)
    code = """
print("A" * 60000)
import sys
sys.stderr.write("B" * 15000)
"""
    result_str = execute_code(code, mode="strict")
    result = json.loads(result_str)
    
    assert len(result["stdout"]) <= 51200 + 100
    assert "[output truncated at 50KB]" in result["stdout"]
    assert len(result["stderr"]) <= 10240 + 100
    assert "[output truncated at 10KB]" in result["stderr"]

def test_execute_code_timeout():
    """Verifies that slow running scripts time out and return the 'timeout' status."""
    code = """
import time
time.sleep(10)
"""
    # Force a very low timeout in settings for the test
    original_timeout = settings.CODE_EXECUTION_TIMEOUT
    settings.CODE_EXECUTION_TIMEOUT = 1
    
    try:
        result_str = execute_code(code, mode="strict")
        result = json.loads(result_str)
        
        assert result["status"] == "timeout"
        assert result["exit_code"] == -1
    finally:
        settings.CODE_EXECUTION_TIMEOUT = original_timeout

def test_execute_code_rpc_tool_call():
    """Verifies that child scripts can invoke harvested tools over the Unix socket RPC."""
    @sovereign_tool(name="dummy_test_tool", category="Test")
    def dummy_test_tool(val1: int, val2: int = 5) -> dict:
        """A simple registered tool for testing RPC integration."""
        return {"result": val1 + val2}
        
    code = """
import json
import kenbun_tools
res = kenbun_tools.dummy_test_tool(val1=10, val2=20)
print(json.dumps(res))
"""
    result_str = execute_code(code, mode="strict")
    result = json.loads(result_str)
    
    assert result["status"] == "success"
    assert result["tool_calls_made"] == 1
    
    # Parse the stdout printed by child
    stdout_json = json.loads(result["stdout"].strip())
    assert stdout_json == {"result": 30}

def test_execute_code_rpc_failing_tool():
    """Verifies that exceptions in parent-executed tools are bubbled back to the child script."""
    @sovereign_tool(name="dummy_failing_tool", category="Test")
    def dummy_failing_tool() -> dict:
        raise ValueError("Something went wrong in parent tool execution")
        
    code = """
import kenbun_tools
try:
    kenbun_tools.dummy_failing_tool()
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
"""
    result_str = execute_code(code, mode="strict")
    result = json.loads(result_str)
    
    assert result["status"] == "success"
    assert "FAILED: Something went wrong in parent tool execution" in result["stdout"]

def test_execute_code_forbidden_tools():
    """Verifies that calling forbidden tools (like execute_code) from the script returns a socket error."""
    code = """
import kenbun_tools
try:
    kenbun_tools._rpc_call("execute_code", code="print('recursed')")
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
"""
    result_str = execute_code(code, mode="strict")
    result = json.loads(result_str)
    
    assert result["status"] == "success"
    assert "FAILED: Tool call to 'execute_code' is forbidden" in result["stdout"]

def test_execute_code_tool_limit():
    """Verifies that exceeding the max tool calls limit returns a socket error."""
    @sovereign_tool(name="dummy_test_tool", category="Test")
    def dummy_test_tool(val1: int) -> dict:
        return {"val": val1}
        
    # Cap max tool calls at 2 for testing
    original_max = settings.CODE_EXECUTION_MAX_TOOL_CALLS
    settings.CODE_EXECUTION_MAX_TOOL_CALLS = 2
    
    code = """
import kenbun_tools
try:
    r1 = kenbun_tools.dummy_test_tool(val1=1)
    r2 = kenbun_tools.dummy_test_tool(val1=2)
    # The 3rd call should trigger the limit
    r3 = kenbun_tools.dummy_test_tool(val1=3)
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
"""
    try:
        result_str = execute_code(code, mode="strict")
        result = json.loads(result_str)
        
        assert result["status"] == "success"
        assert result["tool_calls_made"] == 2
        assert "FAILED: Tool call limit exceeded" in result["stdout"]
    finally:
        settings.CODE_EXECUTION_MAX_TOOL_CALLS = original_max

def test_execute_code_project_mode():
    """Verifies that 'project' mode sets working directory and venv python correctly if possible."""
    code = """
import os
import sys
# Project mode runs in settings.PROJECT_ROOT (the repo root)
print(os.path.abspath(os.getcwd()))
"""
    result_str = execute_code(code, mode="project")
    result = json.loads(result_str)
    
    assert result["status"] == "success"
    # Ensure stdout lists the project root directory path
    cwd_output = result["stdout"].strip()
    assert os.path.isdir(cwd_output)
    # The returned path should match settings.PROJECT_ROOT resolved
    expected_root = str(settings.PROJECT_ROOT.resolve())
    assert cwd_output == expected_root
