#!/usr/bin/env python3
import os
import re
import sys
import time
import json
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Set
import concurrent.futures
import requests

# Insert core directory in sys.path to resolve Kenbun settings if available
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root / "core"))

try:
    from tools.infrastructure.config import settings
    DEFAULT_LLM_URL = settings.PRIMARY_LLM_URL or "http://localhost:11434/v1"
    DEFAULT_MODEL = settings.PRIMARY_LLM_MODEL or "qwen2.5:1.5b"
except ImportError:
    DEFAULT_LLM_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen2.5:1.5b"

# List of all whitelisted / valid tools
VALID_TOOLS = {
    "terminal", "read_file", "write_file", "search_files",
    "patch", "web_search", "web_extract", "execute_code"
}

def load_env_vars() -> Dict[str, str]:
    """Helper to read .env file parameters directly."""
    env = {}
    for p in (project_root / ".env", project_root / "core" / ".env"):
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
    # Overlay real environment variables
    env.update(os.environ)
    return env

def decrypt_value(val: str) -> str:
    """Mock decrypt compatibility to support encrypted environment keys in database/config."""
    if val.startswith("enc:v1:") or val.startswith("enc:"):
        # Real decryption is handled by secret manager; fallback to stripped string for mock compatibility
        return val.split(":", 2)[-1]
    return val

class BatchRunner:
    def __init__(self, args: argparse.Namespace):
        self.dataset_file = Path(args.dataset_file)
        self.batch_size = args.batch_size
        self.run_name = args.run_name
        self.model = args.model
        self.base_url = args.base_url or DEFAULT_LLM_URL
        self.api_key = args.api_key
        self.max_turns = args.max_turns
        self.num_workers = args.num_workers
        self.resume = args.resume
        self.verbose = args.verbose
        self.max_samples = args.max_samples
        self.max_tokens = args.max_tokens
        
        # OpenRouter / Provider options
        self.providers_allowed = args.providers_allowed
        self.providers_ignored = args.providers_ignored
        self.providers_order = args.providers_order
        self.provider_sort = args.provider_sort
        
        # Reasoning options
        self.reasoning_effort = args.reasoning_effort
        self.reasoning_disabled = args.reasoning_disabled
        self.ephemeral_system_prompt = args.ephemeral_system_prompt
        self.prefill_messages_file = args.prefill_messages_file

        # Output Directories Setup
        self.output_dir = Path("data") / self.run_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trajectories_file = self.output_dir / "trajectories.jsonl"
        self.checkpoint_file = self.output_dir / "checkpoint.json"
        self.stats_file = self.output_dir / "statistics.json"

        # Global Session for connection reuse
        self.session = requests.Session()
        
        # Resolved API credentials
        self.env = load_env_vars()
        self.headers = {"Content-Type": "application/json"}
        self._setup_auth()

        # Load completed prompts mapping for checkpointing
        self.completed_prompts: Set[str] = set()
        if self.resume and self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)
                    self.completed_prompts = set(checkpoint_data.get("completed_prompts", []))
                if self.verbose:
                    print(f"Loaded {len(self.completed_prompts)} completed prompts from checkpoint.")
            except Exception as e:
                print(f"Warning: Could not read checkpoint file: {e}")

    def _setup_auth(self):
        # Resolve Authorization Header
        key = self.api_key or self.env.get("PRIMARY_LLM_KEY")
        if not key:
            is_gemini_route = "gemini" in self.base_url.lower() or "googleapis" in self.base_url.lower()
            if is_gemini_route:
                key = self.env.get("GEMINI_API_KEY")
            elif "openai" in self.base_url.lower():
                key = self.env.get("OPENAI_API_KEY")
            elif "deepseek" in self.base_url.lower():
                key = self.env.get("DEEPSEEK_API_KEY")
            elif "openrouter" in self.base_url.lower():
                key = self.env.get("OPENROUTER_API_KEY")
        
        if key:
            decrypted_key = decrypt_value(key)
            self.headers["Authorization"] = f"Bearer {decrypted_key}"

    def _get_prefill_messages(self) -> List[Dict[str, str]]:
        if self.prefill_messages_file:
            p = Path(self.prefill_messages_file)
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"Warning: Failed to load prefill messages: {e}")
        return []

    def execute_prompt_session(self, prompt_index: int, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Runs a single prompt through the isolated agent session loop."""
        prompt_text = prompt_data["prompt"]
        image = prompt_data.get("image") or prompt_data.get("docker_image")
        cwd_override = prompt_data.get("cwd")

        # Establish working directory sandbox boundary
        task_cwd = Path(cwd_override).resolve() if cwd_override else Path.cwd().resolve()
        
        # Normalize target stats mapping
        tool_stats = {t: {"count": 0, "success": 0, "failure": 0} for t in VALID_TOOLS}
        tool_error_counts = {t: 0 for t in VALID_TOOLS}
        
        # Setup dialog history context
        history = []
        system_prompt = self.ephemeral_system_prompt or (
            "You are a helpful assistant equipped with sovereign tools.\n"
            "You can run terminal commands directly by returning code blocks formatted as:\n"
            "```execute\n<shell-command>\n```\n"
        )
        history.append({"role": "system", "content": system_prompt})
        
        # Append prefill examples if provided
        history.extend(self._get_prefill_messages())
        history.append({"role": "user", "content": prompt_text})

        completed = False
        api_calls = 0
        has_reasoning = False
        corrupted = False
        toolsets_used = set()
        
        turn = 0
        while turn < self.max_turns:
            turn += 1
            api_calls += 1
            
            payload = {
                "model": self.model,
                "messages": history,
                "temperature": 0.2
            }
            if self.max_tokens:
                payload["max_tokens"] = self.max_tokens
                
            # Add OpenRouter provider controls
            if "openrouter" in self.base_url.lower():
                payload["provider"] = {}
                if self.providers_allowed:
                    payload["provider"]["allow"] = [p.strip() for p in self.providers_allowed.split(",")]
                if self.providers_ignored:
                    payload["provider"]["ignore"] = [p.strip() for p in self.providers_ignored.split(",")]
                if self.providers_order:
                    payload["provider"]["order"] = [p.strip() for p in self.providers_order.split(",")]
                if self.provider_sort:
                    payload["provider"]["sort"] = self.provider_sort
                    
            # Add Reasoning configurations
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort
            if self.reasoning_disabled:
                payload["reasoning_disabled"] = True

            try:
                resp = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self.headers,
                    timeout=120
                )
                resp.raise_for_status()
                res_data = resp.json()
                assistant_message = res_data["choices"][0]["message"]
                content = assistant_message.get("content") or ""
                
                # Check for native/non-native reasoning tokens
                reasoning = assistant_message.get("reasoning_content") or ""
                if reasoning or "<think>" in content or "<REASONING_SCRATCHPAD>" in content:
                    has_reasoning = True
                    
                history.append({"role": "assistant", "content": content})
                
                # Check for command execution block patterns
                execute_blocks = re.findall(
                    r"```(?::execute|execute|bash|sh)\n(.*?)\n```",
                    content,
                    re.DOTALL | re.IGNORECASE
                )
                if not execute_blocks:
                    execute_blocks = re.findall(
                        r"```(?:execute|bash|sh)\n(.*?)\n```",
                        content,
                        re.DOTALL | re.IGNORECASE
                    )
                
                if not execute_blocks:
                    # No tool calls proposed, task is finished
                    completed = True
                    break
                
                # Parse and run the first proposed tool call
                cmd = execute_blocks[0].strip()
                tool_name = "terminal"
                
                # Check for harvested tool wrap patterns: `kenbun <tool>`
                if cmd.startswith("kenbun "):
                    parts = cmd.split()
                    if len(parts) > 1:
                        proposed_tool = parts[1]
                        if proposed_tool in VALID_TOOLS:
                            tool_name = proposed_tool
                        else:
                            # Flag hallucinated tool name corruption
                            corrupted = True
                            tool_name = proposed_tool
                            if tool_name not in tool_stats:
                                tool_stats[tool_name] = {"count": 0, "success": 0, "failure": 0}
                                tool_error_counts[proposed_tool] = 0
                
                toolsets_used.add(tool_name)
                tool_stats[tool_name]["count"] += 1
                
                # Execute in subprocess
                try:
                    res = subprocess.run(
                        cmd,
                        shell=True,
                        cwd=str(task_cwd),
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    exit_code = res.returncode
                    output = res.stdout + res.stderr
                    
                    if exit_code == 0:
                        tool_stats[tool_name]["success"] += 1
                    else:
                        tool_stats[tool_name]["failure"] += 1
                        tool_error_counts[tool_name] += 1
                        
                except subprocess.TimeoutExpired:
                    exit_code = -1
                    output = "Script timed out and was killed."
                    tool_stats[tool_name]["failure"] += 1
                    tool_error_counts[tool_name] += 1
                except Exception as exc:
                    exit_code = -2
                    output = f"Execution error: {exc}"
                    tool_stats[tool_name]["failure"] += 1
                    tool_error_counts[tool_name] += 1
                
                # Feed tool response back into LLM history context
                history.append({
                    "role": "user",
                    "content": f"[SYSTEM OUT (Command: '{cmd}', Exit Code: {exit_code})]\n{output}"
                })
                
            except Exception as e:
                if self.verbose:
                    print(f"Error during turn {turn} for prompt #{prompt_index}: {e}")
                break

        # Map trajectory structure to ShareGPT-like conversations format
        conversations = []
        for msg in history:
            role = msg["role"]
            content = msg["content"]
            
            # Skip system prompt if ephemeral
            if role == "system" and self.ephemeral_system_prompt:
                continue
                
            if role == "user":
                if content.startswith("[SYSTEM OUT"):
                    conversations.append({"from": "tool", "value": content})
                else:
                    conversations.append({"from": "human", "value": content})
            elif role == "assistant":
                conversations.append({"from": "gpt", "value": content})
            elif role == "system":
                conversations.append({"from": "system", "value": content})

        return {
            "prompt_index": prompt_index,
            "prompt_text": prompt_text,
            "conversations": conversations,
            "metadata": {
                "batch_num": (prompt_index // self.batch_size),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": self.model,
                "image": image,
                "cwd": str(task_cwd)
            },
            "completed": completed,
            "has_reasoning": has_reasoning,
            "corrupted": corrupted,
            "api_calls": api_calls,
            "toolsets_used": list(toolsets_used),
            "tool_stats": tool_stats,
            "tool_error_counts": tool_error_counts
        }

    def run(self):
        """Loads dataset, splits into batches, and runs parallel worker pool."""
        if not self.dataset_file.exists():
            print(f"Error: Dataset file '{self.dataset_file}' not found.")
            sys.exit(1)

        # 1. Parse prompts dataset
        prompts = []
        with open(self.dataset_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    prompts.append(json.loads(line.strip()))
                    
        if self.max_samples and self.max_samples != "all":
            prompts = prompts[:int(self.max_samples)]

        total_prompts = len(prompts)
        print(f"Total prompts in dataset: {total_prompts}")

        # Filter out already completed prompts if resuming
        remaining_prompts = []
        for idx, p in enumerate(prompts):
            p_text = p["prompt"]
            if self.resume and p_text in self.completed_prompts:
                continue
            remaining_prompts.append((idx, p))
            
        print(f"Prompts remaining to process: {len(remaining_prompts)}")
        if not remaining_prompts:
            print("All prompts already processed. Merging trajectories.")
            self._merge_batches()
            return

        # 2. Run workers pool over chunks/batches
        batch_chunks = [
            remaining_prompts[i : i + self.batch_size]
            for i in range(0, len(remaining_prompts), self.batch_size)
        ]

        total_batches = len(batch_chunks)
        print(f"Total batches to process: {total_batches} (Batch Size: {self.batch_size})")

        # Global statistics trackers
        aggregate_stats = {
            "total_runs": 0,
            "completed_runs": 0,
            "runs_with_reasoning": 0,
            "corrupted_runs": 0,
            "total_api_calls": 0,
            "tool_use": {t: {"count": 0, "success": 0, "failure": 0} for t in VALID_TOOLS}
        }
        
        t0 = time.time()

        for chunk_idx, chunk in enumerate(batch_chunks):
            print(f"\nProcessing Batch {chunk_idx + 1}/{total_batches}...")
            batch_results = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                futures = {
                    executor.submit(self.execute_prompt_session, idx, p): (idx, p)
                    for idx, p in chunk
                }
                
                for fut in concurrent.futures.as_completed(futures):
                    idx, p = futures[fut]
                    try:
                        result = fut.result()
                        batch_results.append(result)
                        
                        # Add to checkpoint completed mapping
                        self.completed_prompts.add(p["prompt"])
                        
                        # Update aggregate stats
                        aggregate_stats["total_runs"] += 1
                        if result["completed"]:
                            aggregate_stats["completed_runs"] += 1
                        if result["has_reasoning"]:
                            aggregate_stats["runs_with_reasoning"] += 1
                        if result["corrupted"]:
                            aggregate_stats["corrupted_runs"] += 1
                        aggregate_stats["total_api_calls"] += result["api_calls"]
                        
                        for tool, stats in result["tool_stats"].items():
                            if tool not in aggregate_stats["tool_use"]:
                                aggregate_stats["tool_use"][tool] = {"count": 0, "success": 0, "failure": 0}
                            aggregate_stats["tool_use"][tool]["count"] += stats["count"]
                            aggregate_stats["tool_use"][tool]["success"] += stats["success"]
                            aggregate_stats["tool_use"][tool]["failure"] += stats["failure"]
                            
                        if self.verbose:
                            reasoning_str = "reasoning" if result["has_reasoning"] else "no-reasoning"
                            print(f"Finished prompt #{idx}: completed={result['completed']}, {reasoning_str}")
                    except Exception as e:
                        print(f"Exception for prompt #{idx}: {e}")

            # Write batch file output
            batch_file = self.output_dir / f"batch_{chunk_idx}.jsonl"
            with open(batch_file, "w", encoding="utf-8") as bf:
                for r in batch_results:
                    bf.write(json.dumps(r) + "\n")

            # Update checkpoint state file
            with open(self.checkpoint_file, "w", encoding="utf-8") as cf:
                json.dump({"completed_prompts": list(self.completed_prompts)}, cf, indent=2)

        # 3. Final Merge & Quality Filtering
        self._merge_batches(aggregate_stats)
        
        duration = time.time() - t0
        aggregate_stats["duration_seconds"] = round(duration, 2)
        
        # Save final statistics file
        with open(self.stats_file, "w", encoding="utf-8") as sf:
            json.dump(aggregate_stats, sf, indent=2)
            
        self._print_stats_report(aggregate_stats)

    def _merge_batches(self, aggregate_stats: Dict[str, Any] = None):
        """Combines batch files into trajectories.jsonl applying quality filtering."""
        print("\nMerging batch outputs and executing quality filters...")
        total_filtered_no_reasoning = 0
        total_filtered_corrupted = 0
        total_saved = 0

        # Scan and merge all batch files
        merged_trajectories = []
        for batch_file in self.output_dir.glob("batch_*.jsonl"):
            with open(batch_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line.strip())
                        
                        # Filter 1: No reasoning filter
                        if not r["has_reasoning"]:
                            total_filtered_no_reasoning += 1
                            continue
                            
                        # Filter 2: Corrupted entry filter (hallucinated tools)
                        if r["corrupted"]:
                            total_filtered_corrupted += 1
                            continue
                            
                        merged_trajectories.append(r)
                        total_saved += 1

        with open(self.trajectories_file, "w", encoding="utf-8") as tf:
            for t in merged_trajectories:
                tf.write(json.dumps(t) + "\n")
                
        print(f"Trajectories merged successfully: {self.trajectories_file}")
        print(f"  - Total Trajectories Saved: {total_saved}")
        print(f"  - Filtered (No-Reasoning):   {total_filtered_no_reasoning}")
        print(f"  - Filtered (Corrupted Tools): {total_filtered_corrupted}")

        if aggregate_stats:
            aggregate_stats["filtered_no_reasoning"] = total_filtered_no_reasoning
            aggregate_stats["filtered_corrupted"] = total_filtered_corrupted
            aggregate_stats["saved_trajectories"] = total_saved

    def _print_stats_report(self, stats: Dict[str, Any]):
        """Prints a comprehensive terminal summary statistics report."""
        print("\n" + "=" * 50)
        print("📊 BATCH EXECUTION RUN SUMMARY STATISTICS")
        print("=" * 50)
        print(f"Total Worker Runs:         {stats['total_runs']}")
        print(f"Successfully Completed:     {stats['completed_runs']}")
        print(f"Total Trajectories Saved:   {stats.get('saved_trajectories', 0)}")
        print(f"Filtered (No-Reasoning):     {stats.get('filtered_no_reasoning', 0)}")
        print(f"Filtered (Corrupted Tools):   {stats.get('filtered_corrupted', 0)}")
        print(f"Total LLM API Calls:        {stats['total_api_calls']}")
        print(f"Total Processing Duration:   {stats.get('duration_seconds', 0.0)}s")
        print("-" * 50)
        print("🔧 Tool Usage Distribution:")
        for tool, details in stats["tool_use"].items():
            if details["count"] > 0:
                print(f"  • {tool:18} count: {details['count']:4} | success: {details['success']:4} | failure: {details['failure']:4}")
        print("=" * 50 + "\n")

def list_distributions():
    """Prints pre-configured toolset distributions."""
    print("\nAvailable toolset distributions:")
    print("  • default:     Standard system utilities (terminal, read_file, write_file, patch)")
    print("  • web:         Web interaction (web_search, web_extract, terminal)")
    print("  • execution:   Programmatic sandbox execution (execute_code, terminal)")
    print("  • full:        All active harvested sovereign tools enabled\n")

def main():
    parser = argparse.ArgumentParser(description="Kenbun Agent Batch Processing Trajectory Generator")
    parser.add_argument("--dataset_file", required=True, help="Path to JSONL prompts dataset")
    parser.add_argument("--batch_size", type=int, required=True, help="Number of prompts per batch")
    parser.add_argument("--run_name", required=True, help="Unique name identifier for output subdirectory")
    parser.add_argument("--distribution", default="default", help="Toolset distribution package")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Primary LLM completion model key")
    parser.add_argument("--base_url", help="Override completion endpoint base URL")
    parser.add_argument("--api_key", help="Authorization API Key credential")
    parser.add_argument("--max_turns", type=int, default=10, help="Max agent tool loops per session")
    parser.add_argument("--num_workers", type=int, default=4, help="Parallel worker threads count")
    parser.add_argument("--resume", action="store_true", help="Resume processing from last saved checkpoint")
    parser.add_argument("--verbose", action="store_true", help="Enable diagnostic verbose logging")
    parser.add_argument("--max_samples", help="Limit execution to first N samples from dataset")
    parser.add_argument("--max_tokens", type=int, help="Optional constraint for response token generation limit")
    
    # OpenRouter Specific Options
    parser.add_argument("--providers_allowed", help="OpenRouter allowed providers filter")
    parser.add_argument("--providers_ignored", help="OpenRouter ignored providers filter")
    parser.add_argument("--providers_order", help="OpenRouter preferred providers priority order")
    parser.add_argument("--provider_sort", help="OpenRouter provider sorting metric")
    
    # Reasoning Parameters
    parser.add_argument("--reasoning_effort", help="Model reasoning effort: low, medium, high")
    parser.add_argument("--reasoning_disabled", action="store_true", help="Disable reasoning/thinking tokens completely")
    parser.add_argument("--ephemeral_system_prompt", help="System prompt override (not saved to output)")
    parser.add_argument("--prefill_messages_file", help="JSON file with prefill messages for few-shot priming")
    
    # Auxiliary Command Actions
    parser.add_argument("--list_distributions", action="store_true", help="List available distributions and exit")

    args = parser.parse_args()

    if args.list_distributions:
        list_distributions()
        sys.exit(0)

    runner = BatchRunner(args)
    runner.run()

if __name__ == "__main__":
    main()
