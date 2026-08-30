import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Insert project root and scripts/maintenance in sys.path to resolve batch_runner
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts" / "maintenance"))

import batch_runner

@pytest.fixture
def temp_dataset():
    """Create a temporary prompts dataset for batch runner tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "prompts.jsonl"
        with open(dataset_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"prompt": "Prompt 1: Echo hello", "image": "python:3.11-slim"}) + "\n")
            f.write(json.dumps({"prompt": "Prompt 2: Find file", "cwd": "/tmp"}) + "\n")
            f.write(json.dumps({"prompt": "Prompt 3: Exceed limit"}) + "\n")
        yield dataset_path

def test_batch_runner_args_parsing():
    """Verifies that batch runner parses CLI arguments correctly."""
    parser = argparse_mock = MagicMock()
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_parse.return_value = MagicMock(
            dataset_file="data/prompts.jsonl",
            batch_size=2,
            run_name="test_run",
            distribution="default",
            model="test-model",
            base_url="http://localhost:11434/v1",
            api_key=None,
            max_turns=5,
            num_workers=2,
            resume=False,
            verbose=False,
            max_samples=None,
            max_tokens=None,
            providers_allowed=None,
            providers_ignored=None,
            providers_order=None,
            provider_sort=None,
            reasoning_effort=None,
            reasoning_disabled=False,
            ephemeral_system_prompt=None,
            prefill_messages_file=None,
            list_distributions=False
        )
        # Test constructor
        runner = batch_runner.BatchRunner(mock_parse.return_value)
        assert runner.run_name == "test_run"
        assert runner.batch_size == 2
        assert runner.num_workers == 2

@patch("requests.Session.post")
def test_execute_prompt_session_no_tool(mock_post, temp_dataset):
    """Verifies executing a prompt that results in a direct response (no tool usage)."""
    # Mock LLM response: direct completion
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "<think>Thinking process...</think>\nHello! I am finished."
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    args = MagicMock(
        dataset_file=str(temp_dataset),
        batch_size=1,
        run_name="test_direct",
        distribution="default",
        model="test-model",
        base_url="http://localhost:11434/v1",
        api_key=None,
        max_turns=3,
        num_workers=1,
        resume=False,
        verbose=False,
        max_samples="1",
        max_tokens=None,
        providers_allowed=None,
        providers_ignored=None,
        providers_order=None,
        provider_sort=None,
        reasoning_effort=None,
        reasoning_disabled=False,
        ephemeral_system_prompt=None,
        prefill_messages_file=None
    )

    runner = batch_runner.BatchRunner(args)
    res = runner.execute_prompt_session(0, {"prompt": "Hello!"})

    assert res["completed"] is True
    assert res["has_reasoning"] is True
    assert res["corrupted"] is False
    assert len(res["conversations"]) == 3  # system + human + gpt
    assert res["conversations"][0]["from"] == "system"
    assert res["conversations"][1]["from"] == "human"
    assert res["conversations"][2]["from"] == "gpt"
    assert "finished." in res["conversations"][2]["value"]

@patch("requests.Session.post")
@patch("subprocess.run")
def test_execute_prompt_session_with_tool(mock_subrun, mock_post, temp_dataset):
    """Verifies executing a prompt that triggers a tool call (terminal command)."""
    # Mock LLM Response 1: trigger tool
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "<REASONING_SCRATCHPAD>Must search files</REASONING_SCRATCHPAD>\n```execute\nkenbun search_files query=\"test\"\n```"
                }
            }
        ]
    }
    
    # Mock LLM Response 2: completed
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Found the files. Finished."
                }
            }
        ]
    }
    
    mock_post.side_effect = [mock_resp1, mock_resp2]

    # Mock command execution output
    mock_subrun_res = MagicMock()
    mock_subrun_res.returncode = 0
    mock_subrun_res.stdout = "src/main.py\nsrc/utils.py"
    mock_subrun_res.stderr = ""
    mock_subrun.return_value = mock_subrun_res

    args = MagicMock(
        dataset_file=str(temp_dataset),
        batch_size=1,
        run_name="test_tool",
        distribution="default",
        model="test-model",
        base_url="http://localhost:11434/v1",
        api_key=None,
        max_turns=3,
        num_workers=1,
        resume=False,
        verbose=False,
        max_samples="1",
        max_tokens=None,
        providers_allowed=None,
        providers_ignored=None,
        providers_order=None,
        provider_sort=None,
        reasoning_effort=None,
        reasoning_disabled=False,
        ephemeral_system_prompt=None,
        prefill_messages_file=None
    )

    runner = batch_runner.BatchRunner(args)
    res = runner.execute_prompt_session(0, {"prompt": "Find test files"})

    assert res["completed"] is True
    assert res["has_reasoning"] is True
    assert res["corrupted"] is False
    assert len(res["conversations"]) == 5  # system + human + gpt + tool + gpt
    assert res["conversations"][0]["from"] == "system"
    assert res["conversations"][1]["from"] == "human"
    assert res["conversations"][2]["from"] == "gpt"
    assert res["conversations"][3]["from"] == "tool"
    assert res["conversations"][4]["from"] == "gpt"
    assert "search_files" in res["toolsets_used"]
    assert res["tool_stats"]["search_files"]["count"] == 1
    assert res["tool_stats"]["search_files"]["success"] == 1

@patch("requests.Session.post")
def test_quality_filtering_no_reasoning(mock_post, temp_dataset):
    """Verifies that trajectories with zero reasoning are filtered out during merge."""
    # Mock LLM response: no think block or reasoning tokens
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This response contains no reasoning token or block."
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    args = MagicMock(
        dataset_file=str(temp_dataset),
        batch_size=3,
        run_name="test_filter_reasoning",
        distribution="default",
        model="test-model",
        base_url="http://localhost:11434/v1",
        api_key=None,
        max_turns=2,
        num_workers=1,
        resume=False,
        verbose=False,
        max_samples="3",
        max_tokens=None,
        providers_allowed=None,
        providers_ignored=None,
        providers_order=None,
        provider_sort=None,
        reasoning_effort=None,
        reasoning_disabled=False,
        ephemeral_system_prompt=None,
        prefill_messages_file=None
    )

    runner = batch_runner.BatchRunner(args)
    
    # Run the full batch processing
    runner.run()
    
    # Check output stats
    assert runner.stats_file.exists()
    with open(runner.stats_file, "r") as sf:
        stats = json.load(sf)
        
    assert stats["total_runs"] == 3
    assert stats["runs_with_reasoning"] == 0
    assert stats["filtered_no_reasoning"] == 3
    assert stats["saved_trajectories"] == 0

@patch("requests.Session.post")
def test_checkpoint_and_resume(mock_post, temp_dataset):
    """Verifies that resuming from an interrupted run loads checkpoint and skips processed prompts."""
    # Setup completed prompt in checkpoint
    run_name = "test_resume"
    output_dir = Path("data") / run_name
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = output_dir / "checkpoint.json"
    
    with open(checkpoint_file, "w", encoding="utf-8") as cf:
        json.dump({"completed_prompts": ["Prompt 1: Echo hello"]}, cf)

    # Mock response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "<think>Thinking</think>\nDone."
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    args = MagicMock(
        dataset_file=str(temp_dataset),
        batch_size=10,
        run_name=run_name,
        distribution="default",
        model="test-model",
        base_url="http://localhost:11434/v1",
        api_key=None,
        max_turns=2,
        num_workers=1,
        resume=True,
        verbose=False,
        max_samples="all",
        max_tokens=None,
        providers_allowed=None,
        providers_ignored=None,
        providers_order=None,
        provider_sort=None,
        reasoning_effort=None,
        reasoning_disabled=False,
        ephemeral_system_prompt=None,
        prefill_messages_file=None
    )

    runner = batch_runner.BatchRunner(args)
    assert "Prompt 1: Echo hello" in runner.completed_prompts
    
    # We should only process prompts 2 and 3
    # Let's intercept execution
    with patch.object(runner, "execute_prompt_session", return_value={
        "completed": True, "has_reasoning": True, "corrupted": False, "api_calls": 1,
        "toolsets_used": [], "tool_stats": {}, "tool_error_counts": {}
    }) as mock_exec:
        runner.run()
        # Should be called twice (for prompt 2 and prompt 3)
        assert mock_exec.call_count == 2
