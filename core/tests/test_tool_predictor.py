import pytest
from core.tools.cli.tool_predictor import predict_tool_command

def test_predict_scan_repo():
    assert predict_tool_command("scan repo") == "/run scan_repo project_path=."
    assert predict_tool_command("scan files") == "/run scan_repo project_path=."
    assert predict_tool_command("project map") == "/run scan_repo project_path=."
    assert predict_tool_command("Please scan the repo now.") == "/run scan_repo project_path=."
    assert predict_tool_command("Generate a project map") == "/run scan_repo project_path=."

def test_predict_audit():
    assert predict_tool_command("audit package") == "/run audit_package_safety"
    assert predict_tool_command("audit safety") == "/run audit_package_safety"
    assert predict_tool_command("please run audit safety") == "/run audit_package_safety"

def test_predict_lint():
    assert predict_tool_command("lint file.py") == "/run autofix_linter file_path=file.py"
    assert predict_tool_command("lint core/tools/cli/engine.py") == "/run autofix_linter file_path=core/tools/cli/engine.py"
    assert predict_tool_command("fix syntax in test.py") == "/run autofix_linter file_path=test.py"
    assert predict_tool_command("fix syntax for engine.py") == "/run autofix_linter file_path=engine.py"
    # Natural punctuation stripping
    assert predict_tool_command("lint file.py, please?") == "/run autofix_linter file_path=file.py"

def test_predict_checkpoint():
    assert predict_tool_command("checkpoint engine.py") == "/run save_checkpoint file_path=engine.py label=pre_fix"
    assert predict_tool_command("checkpoint core/tools/cli/engine.py.") == "/run save_checkpoint file_path=core/tools/cli/engine.py label=pre_fix"

def test_predict_recall():
    assert predict_tool_command("recall TypeError") == '/run recall_fix error_message="TypeError"'
    assert predict_tool_command("recall TypeError: 'int' object is not iterable") == '/run recall_fix error_message="TypeError: \'int\' object is not iterable"'
    assert predict_tool_command("recall \"name 'foo' is not defined\"") == "/run recall_fix error_message=\"name 'foo' is not defined\""

def test_predict_research():
    assert predict_tool_command("research Next.js server actions") == '/run research_official_docs query="Next.js server actions"'
    assert predict_tool_command("research \"asyncio loops\"") == '/run research_official_docs query="asyncio loops"'

def test_no_prediction():
    assert predict_tool_command("hello there") is None
    assert predict_tool_command("how do I build a server?") is None
    assert predict_tool_command("") is None
