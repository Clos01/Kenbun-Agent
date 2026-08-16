import pytest
import json
from tools.infrastructure.git_watcher_tools import _parse_github_repo, apply_git_patch
from tools.registry import registry

def test_parse_github_repo():
    assert _parse_github_repo("https://github.com/Clos01/Kenbun-Agent") == ("Clos01", "Kenbun-Agent")
    assert _parse_github_repo("git@github.com:Clos01/Kenbun-Agent.git") == ("Clos01", "Kenbun-Agent")
    assert _parse_github_repo("Clos01/Kenbun-Agent") == ("Clos01", "Kenbun-Agent")
    assert _parse_github_repo("invalid-repo-url") is None

def test_apply_git_patch_safety_block():
    # Attempt to write a file outside project root using path traversal
    unsafe_changes = json.dumps({
        "status": "success",
        "repo": "Clos01/Kenbun-Agent",
        "latest_sha": "abc123sha",
        "changes": [
            {
                "file_path": "../../../etc/passwd",
                "content": "malicious content",
                "action": "create"
            }
        ]
    })
    
    res = apply_git_patch(unsafe_changes)
    assert any(word in res.upper() for word in ["SECURITY", "BREACH", "BLOCK", "OUTSIDE"])

@pytest.mark.asyncio
async def test_git_push_integration_pipeline_registered():
    pipelines = registry.get_all_pipelines()
    assert "git_push_integration" in pipelines
    assert pipelines["git_push_integration"].name == "git_push_integration"
