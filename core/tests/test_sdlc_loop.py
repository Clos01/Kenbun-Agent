from tools.registry import registry
from tools.infrastructure.server import sync_jira_issue, create_bitbucket_pr

def test_sdlc_loop_registered():
    pipelines = registry.get_all_pipelines()
    assert "sdlc_loop" in pipelines
    
    sdlc_loop = pipelines["sdlc_loop"]
    assert sdlc_loop.name == "sdlc_loop"
    assert "SDLC" in sdlc_loop.description
    assert callable(sdlc_loop.builder)

def test_sync_jira_issue_mock():
    # Verify sync_jira_issue runs in mock mode when env vars are missing
    res = sync_jira_issue("JIRA-1234", "Done")
    assert "Jira Sync: JIRA-1234" in res
    assert "SIMULATED" in res
    assert "Done" in res

def test_create_bitbucket_pr_mock():
    # Verify create_bitbucket_pr runs in mock mode when env vars are missing
    res = create_bitbucket_pr("my-repo", "feature/branch", "master", "Title Fix")
    assert "Bitbucket Pull Request" in res
    assert "SIMULATED" in res
    assert "my-repo" in res
