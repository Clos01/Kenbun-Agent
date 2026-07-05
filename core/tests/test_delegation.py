import json
from unittest.mock import patch, AsyncMock
import pytest

from tools.strategy.delegation_tool import delegate_task, get_tools_for_toolsets

def test_get_tools_for_toolsets():
    # 1. Test filtering by 'file' toolset
    file_tools = get_tools_for_toolsets(["file"])
    assert "view_file" in file_tools
    assert "scan_repo" in file_tools
    assert "run_code_safely" not in file_tools
    assert "research_with_gemini" not in file_tools
    
    # 2. Test filtering by 'terminal' and 'web'
    term_web_tools = get_tools_for_toolsets(["terminal", "web"])
    assert "run_code_safely" in term_web_tools
    assert "research_with_gemini" in term_web_tools
    assert "view_file" not in term_web_tools
    
    # 3. Test orchestrator flag includes delegate_task
    orch_tools = get_tools_for_toolsets(["file"], is_orchestrator=True)
    assert "delegate_task" in orch_tools

@pytest.mark.asyncio
async def test_delegate_single_task():
    # Mock spawn_swarm to prevent calling real LLMs during pytest
    with patch("tools.strategy.delegation_tool.spawn_swarm", new_callable=AsyncMock) as mock_spawn:
        mock_spawn.return_value = "Test successfully verified in sandbox."
        
        res = await delegate_task(
            goal="Test single task delegation",
            context="Verify mocking works",
            toolsets=["file"]
        )
        
        assert "Test successfully verified" in res
        mock_spawn.assert_called_once()
        args, kwargs = mock_spawn.call_args
        assert "Test single task delegation" in args[0]
        assert "view_file" in args[1]
        assert "run_code_safely" not in args[1]

@pytest.mark.asyncio
async def test_delegate_parallel_batch():
    with patch("tools.strategy.delegation_tool.spawn_swarm", new_callable=AsyncMock) as mock_spawn:
        mock_spawn.side_effect = [
            "Research result A",
            "Research result B"
        ]
        
        tasks_batch = [
            {"goal": "Research topic A", "context": "Details A", "toolsets": ["web"]},
            {"goal": "Research topic B", "context": "Details B", "toolsets": ["web"]}
        ]
        
        res = await delegate_task(tasks=tasks_batch)
        
        assert "Subagent Task 1 Summary" in res
        assert "Research result A" in res
        assert "Subagent Task 2 Summary" in res
        assert "Research result B" in res
        assert mock_spawn.call_count == 2
