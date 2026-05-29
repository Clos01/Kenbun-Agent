import asyncio
from tools.infrastructure.orchestrator import spawn_swarm
import os

async def main():
    print("🚀 Triggering Swarm Objective for Mission Control...")
    objective = "Analyze the current security of the Kenbun/core codebase and recommend one hardening step."
    
    # Mock tools for the demo
    mock_tools = {
        "scan_repo": lambda **kwargs: "Mock Repo Map: core/, tools/, ingestion/",
        "recall_fix": lambda **kwargs: "No past fixes found for security hardening.",
        "save_checkpoint": lambda **kwargs: "Checkpoint saved.",
        "review_code_with_gemini": lambda **kwargs: "Gemini analysis: Consider using environment variables for API keys.",
        "run_code_safely": lambda **kwargs: "Sandbox test passed.",
        "remember_fix": lambda **kwargs: "Lesson saved to memory.",
        "research_with_gemini": lambda **kwargs: "Research result: Best practices for security in Python agents.",
        "consult_supervisor": lambda **kwargs: "Supervisor approved the hardening plan.",
        "view_file": lambda **kwargs: "def some_code(): pass",
    }
    
    # This will trigger the Queen to decompose the task and execute
    await spawn_swarm(objective, tools=mock_tools)

if __name__ == "__main__":
    asyncio.run(main())
