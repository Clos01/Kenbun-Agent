import pytest
from pathlib import Path
from tools.audit.linter_autofix import autofix_linter, _resolve_paths, SecurityException
from tools.infrastructure.config import settings

@pytest.mark.smoke
def test_resolve_paths_valid():
    """Verify that valid paths within project workspace resolve cleanly."""
    file_path = settings.PROJECT_ROOT / "core" / "tools" / "infrastructure" / "server.py"
    res_file, res_proj = _resolve_paths(str(file_path), str(settings.PROJECT_ROOT))
    assert res_file == file_path.resolve()
    assert res_proj == settings.PROJECT_ROOT.resolve()

@pytest.mark.smoke
def test_resolve_paths_invalid_traversal():
    """Verify that path traversal outside project workspace throws SecurityException."""
    # Let's try passing /etc/passwd or a path above project root
    traversal_path = settings.PROJECT_ROOT / ".." / ".."
    with pytest.raises(SecurityException) as exc_info:
        _resolve_paths(str(traversal_path), str(settings.PROJECT_ROOT))
    assert "SECURITY BREACH" in str(exc_info.value)

@pytest.mark.smoke
def test_autofix_nonexistent():
    """Verify nonexistent file returns a clean error message."""
    res = autofix_linter("non_existent_file_xyz.py")
    assert "does not exist on disk" in res

@pytest.mark.smoke
def test_autofix_python_valid(tmp_path):
    """Verify auto-fixing a dummy Python file with unused imports works successfully."""
    # Create dummy Python file inside settings.PROJECT_ROOT (or tmp_path, let's use tmp_path as workspace to avoid polluting active files)
    workspace = tmp_path
    dummy_file = workspace / "dummy.py"
    
    # Write python code with unused import and a formatting misalignment
    dummy_file.write_text(
        "import os\n"
        "import sys\n"
        "\n"
        "def hello():\n"
        "    print( 'hello world' )\n"
        "    return 1\n",
        encoding="utf-8"
    )
    
    # Run autofix_linter on it
    res = autofix_linter(str(dummy_file), str(workspace))
    
    assert "SUCCESS" in res
    
    # Check that isort/black formatted and autoflake removed unused imports
    content = dummy_file.read_text(encoding="utf-8")
    
    # autoflake should have removed unused imports os and sys
    assert "import os" not in content
    assert "import sys" not in content
    
    # black should have formatted the prints from ( 'hello world' ) to ('hello world')
    assert "print(\"hello world\")" in content or "print('hello world')" in content

@pytest.mark.smoke
def test_autofix_python_syntax_error(tmp_path):
    """Verify auto-fixing a Python file with syntax error aborts formatting."""
    workspace = tmp_path
    dummy_file = workspace / "broken.py"
    
    # Syntax error: unclosed parenthesis
    dummy_file.write_text(
        "import os\n"
        "def broken(\n",
        encoding="utf-8"
    )
    
    res = autofix_linter(str(dummy_file), str(workspace))
    assert "active syntax errors and cannot be safely auto-fixed" in res
