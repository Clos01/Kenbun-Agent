from unittest.mock import AsyncMock, patch

import pytest

from tools.execution.subagent.definition import SubagentResult
from tools.strategy.delegation_tool import (
    _toolsets_restricted,
    delegate_task,
    get_tools_for_toolsets,
)


def _sub_result(output: str, ok: bool = True) -> SubagentResult:
    return SubagentResult(task_label="t", ok=ok, output=output, provider="in-process-swarm")


def test_get_tools_for_toolsets():
    file_tools = get_tools_for_toolsets(["file"])
    assert "view_file" in file_tools
    assert "scan_repo" in file_tools

    term_web_tools = get_tools_for_toolsets(["terminal", "web"])
    assert "run_code_safely" in term_web_tools
    assert "research_with_gemini" in term_web_tools

    orch_tools = get_tools_for_toolsets(["file"], is_orchestrator=True)
    assert "delegate_task" in orch_tools


# ---- DSH-04 slice 2: the leaf path goes through the subagent seam ----
@pytest.mark.asyncio
async def test_delegate_single_task_routes_through_the_seam():
    with patch("tools.execution.subagent.subagent.run") as mock_run:
        mock_run.return_value = _sub_result("Test successfully verified in sandbox.")

        res = await delegate_task(goal="Test single task delegation",
                                  context="Verify wiring")   # default toolsets -> seam

        assert "Test successfully verified" in res
        assert "Subagent Task Summary" in res
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert mock_run.call_args[0][0] == "Test single task delegation"
        assert kwargs["context"] == "Verify wiring"


@pytest.mark.asyncio
async def test_delegate_parallel_batch_routes_through_the_seam():
    with patch("tools.execution.subagent.subagent.run") as mock_run:
        mock_run.side_effect = [_sub_result("Research result A"), _sub_result("Research result B")]

        res = await delegate_task(tasks=[
            {"goal": "Research topic A", "context": "Details A"},
            {"goal": "Research topic B", "context": "Details B"},
        ])

        assert "Subagent Task 1 Summary" in res and "Research result A" in res
        assert "Subagent Task 2 Summary" in res and "Research result B" in res
        assert mock_run.call_count == 2


@pytest.mark.asyncio
async def test_a_failed_subagent_result_surfaces_as_an_error_line():
    with patch("tools.execution.subagent.subagent.run") as mock_run:
        mock_run.return_value = SubagentResult(
            task_label="t", ok=False, output="partial", provider="x",
            error="provider unavailable (quota / decomposition)",
        )
        res = await delegate_task(goal="do it")
        assert "❌" in res and "quota" in res


# ---- role="orchestrator" keeps the original spawn_swarm route untouched ----
@pytest.mark.asyncio
async def test_orchestrator_role_still_uses_spawn_swarm_directly():
    with patch("tools.strategy.delegation_tool.spawn_swarm", new_callable=AsyncMock) as mock_spawn, \
         patch("tools.execution.subagent.subagent.run") as mock_seam:
        mock_spawn.return_value = "nested result"
        res = await delegate_task(goal="coordinate", role="orchestrator")
        assert "nested result" in res
        mock_spawn.assert_called_once()
        mock_seam.assert_not_called()


# ---- a restricted toolset must NOT widen via the seam ----
@pytest.mark.parametrize("toolsets,restricted", [
    (None, False), ("", False), ([], False),
    (["terminal", "file", "web"], False),
    ("terminal,file,web", False),
    (["file"], True), ("file", True), ("file,web", True),
    ('["file"]', True),
])
def test_toolsets_restricted_classification(toolsets, restricted):
    assert _toolsets_restricted(toolsets) is restricted


@pytest.mark.asyncio
async def test_restricted_toolset_keeps_the_scoped_spawn_swarm_route():
    with patch("tools.strategy.delegation_tool.spawn_swarm", new_callable=AsyncMock) as mock_spawn, \
         patch("tools.execution.subagent.subagent.run") as mock_seam:
        mock_spawn.return_value = "scoped result"
        res = await delegate_task(goal="read a file", toolsets=["file"])
        assert "scoped result" in res
        mock_seam.assert_not_called()
        # the scoped tool dict actually reached spawn_swarm
        assert "view_file" in mock_spawn.call_args[0][1]


def test_local_view_file_rejects_a_sibling_dir_that_shares_the_root_prefix(tmp_path, monkeypatch):
    import tools.strategy.delegation_tool as dt

    root = tmp_path / "project"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "ok.txt").write_text("inside")
    sibling = tmp_path / "project_secrets"
    sibling.mkdir()
    (sibling / "leak.txt").write_text("SECRET")

    monkeypatch.setattr(dt.settings, "PROJECT_ROOT", str(root), raising=False)
    view = get_tools_for_toolsets(["file"])["view_file"]

    assert view(str(root / "sub" / "ok.txt")) == "inside"
    with pytest.raises(PermissionError):
        view(str(sibling / "leak.txt"))
