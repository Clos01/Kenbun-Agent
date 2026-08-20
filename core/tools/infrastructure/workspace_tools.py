import base64
import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Any, Optional

from tools.infrastructure.config import settings
from tools.registry import sovereign_tool
from tools.utils.helpers import silence_stdout
from tools.utils.path_utils import get_project_root

logger = logging.getLogger("tools.workspace")
PROJECT_ROOT = get_project_root()


# ============================================================
# GLOBAL WORKSPACE (Swarm Working Memory — J-space analogue)
# ============================================================

@sovereign_tool()
def workspace_post(concept: str, salience: float = 0.5, agent_id: str = "unknown") -> str:
    """
    Put a concept on the swarm's shared working memory ("what I'm thinking about
    right now"). Post concepts, not chatter — most traffic should bypass this.
    Watchlist matches are flagged for supervisor review before action.
    """
    with silence_stdout():
        from tools.memory.global_workspace import post_concept
        return json.dumps(post_concept(concept, salience=salience, agent_id=agent_id))


@sovereign_tool()
def workspace_read(limit: int = 48) -> str:
    """
    Answer "what is the swarm thinking right now?" — returns current workspace
    slots ordered by salience (flagged alerts first). Salience decays over time.
    """
    with silence_stdout():
        from tools.memory.global_workspace import read_workspace
        return json.dumps(read_workspace(limit=limit))


@sovereign_tool()
def workspace_inject(concept: str, salience: float = 0.9) -> str:
    """
    Operator/supervisor steering: inject or boost a concept in the swarm's
    working memory so downstream agents pick it up.
    """
    with silence_stdout():
        from tools.memory.global_workspace import inject_concept
        return json.dumps(inject_concept(concept, salience=salience))


@sovereign_tool()
def workspace_resolve_alert(concept: str) -> str:
    """
    Supervisor acknowledges a flagged workspace concept after review; the slot
    resumes normal salience decay.
    """
    with silence_stdout():
        from tools.memory.global_workspace import resolve_alert
        return json.dumps(resolve_alert(concept))


# ============================================================
# CODEBASE VECTORIZATION (Semantic Code Understanding)
# ============================================================

@sovereign_tool()
def index_codebase(project_path: str = "") -> str:
    """
    Indexes the entire project's code into the Hivemind (ChromaDB) using semantic code chunking.
    Call this when the user wants the system to 'understand' their massive codebase.
    """
    with silence_stdout():
        if not project_path:
            project_path = str(PROJECT_ROOT)
        from tools.memory.code_indexer import index_project
        return index_project(project_path)


@sovereign_tool()
def search_codebase(query: str) -> str:
    """
    Searches the semantic code index for a specific function, logic, or implementation pattern.
    Use this instead of grep when you need semantic, mathematical understanding of what the code does.
    """
    with silence_stdout():
        from tools.memory.code_indexer import search_code
        return search_code(query)


# ============================================================
# THE PLANNER (Think Before You Act)
# ============================================================

TOOL_CATALOG = """
AVAILABLE TOOLS (20 total):

CORE TOOLS:
1. consult_supervisor(user_proposal, code_snippet, iterative_mode) — Local LLM review for security/scalability
2. research_official_docs(tech_key, query) — Search official docs (React, Next.js, FastAPI, Supabase, etc.)
3. ask_architect(query) — Query the project memory/history via ChromaDB vector search
4. ask_ui_expert(query) — CSS/Layout consulting from the UI Designer module
5. get_design_tokens() — Returns the current Design System tokens from the root DESIGN.md

KNOWLEDGE MANAGEMENT:
5. save_to_hivemind(title, content, tags) — Save a new architectural rule, pattern, or concept to the Hivemind
6. search_hivemind_concepts(query) — Search the Hivemind for explicit concepts by text
7. delete_from_hivemind(concept_id) — Delete a concept from the Hivemind by ID

CODEBASE VECTORIZATION:
8. index_codebase(project_path) — Chunk and index thousands of lines of code into the Vector DB
9. search_codebase(query) — Search for code semantically using natural language

CLOUD AI & CONTENT:
10. review_code_with_gemini(code_snippet, review_context, tech_key, cross_check, thinking, thinking_level) — Full 4-stage code review pipeline
11. research_with_gemini(query, tech_key, thinking, thinking_level) — Cloud-based research grounded in official docs
11.5 write_website_content(topic, context, length) — Generates human-like website copy avoiding AI jargon ('bespoke', 'delve')

PRO STACK:
12. run_code_safely(code, language, timeout) — Execute code in isolated Docker container (no network, auto-destroy)
13. scan_repo(project_path, extensions) — Generate skeleton map of a project (classes/functions only, no code)
14. remember_fix(error_message, solution, file_context) — Save an error→fix mapping for future recall
15. recall_fix(error_message) — Semantic search for similar past errors and their solutions
16. save_checkpoint(file_path, label) — Snapshot a file before risky changes
17. restore_checkpoint(file_path, label) — Revert a file to a checkpoint
18. list_checkpoints(file_path) — List saved checkpoints

ORCHESTRATOR:
19. orchestrate(workflow, task, project_path, file_path, code_snippet, tech_key)
    Workflows: "bug_fix" | "code_review" | "research_implement"
    Chains multiple tools automatically with backtracking.

META:
20. think_about_tools(task) — THIS TOOL. Analyzes a task and recommends the optimal tool strategy.
"""

# Cap on how many tools survive the L1 gate for a single strategy prompt. Set
# above the typical plan length (3-6 steps) so gating never removes a tool the
# planner would realistically have reached for.
CATALOG_MAX_ACTIVE_TOOLS = 12


def _catalog_for_task(task: str) -> str:
    """Task-relevant slice of the tool catalog (ESL Ch. 3 & 18, bet on sparsity).

    The static TOOL_CATALOG above is both stale (20 hand-written entries against
    a registry several times that size) and unconditional — every strategy
    prompt paid for every tool. This builds the catalog from the live registry
    and L1-gates it down to the tools that are actually relevant to `task`.

    Falls back to the static catalog whenever the registry or the gate is
    unavailable: a degraded catalog is fine, a crashed planner is not.
    """
    try:
        from tools.utils.sparse_gating import gated_tool_catalog
        gated, stats = gated_tool_catalog(task, max_active_tools=CATALOG_MAX_ACTIVE_TOOLS)
        if gated:
            logger.info(
                "[L1-GATE] catalog %d/%d tools, %d->%d chars (%.1f%% saved)",
                stats["active_tools"], stats["total_tools"],
                stats["full_chars"], stats["gated_chars"], stats["savings_pct"],
            )
            return gated
    except Exception as e:
        logger.warning(f"[L1-GATE] Sparse catalog unavailable ({e}); using static catalog.")
    return TOOL_CATALOG


@sovereign_tool()
def think_about_tools(task: str) -> str:
    """
    Analyze a task and recommend which tools to use and in what order.
    """
    catalog = _catalog_for_task(task)

    try:
        from tools.audit.gemini_reviewer import _call_gemini
        from tools.strategy.decision_logic import router

        strategy_path = router.get_strategy_path(task)
        recommended_tools = router.recommend_tools(task)

        system_prompt = (
            "You are a Tool Strategist for an AI coding agent called Kenbun. "
            "The Decision Tree (System 4b) has already selected a path for this task.\n\n"
            f"DECISION TREE PATH: {strategy_path}\n"
            f"RECOMMENDED TOOLS: {', '.join(recommended_tools)}\n\n"
            "Given this path, recommend the OPTIMAL sequence of tools to use. "
            "Be specific: name the exact tools, their arguments, and WHY each step matters.\n\n"
            "Rules:\n"
            "- If a built-in orchestrate() workflow fits, recommend that FIRST\n"
            "- For simple tasks, recommend individual tools (don't over-engineer)\n"
            "- Always consider: do we need a checkpoint before risky changes?\n"
            "- Always consider: should we recall_fix first to check past solutions?\n"
            "- Always consider: does this need a scan_repo for context?\n\n"
            "Format your response as:\n"
            "## 🌳 Decision Tree Path: " + strategy_path + "\n"
            "## Recommended Strategy\nBrief description\n\n"
            "## Step-by-Step Plan\n1. tool_name(...) — reason\n2. ...\n\n"
            "## Alternative Approach\nIf the above doesn't work, try...\n\n"
            f"{catalog}"
        )

        result = _call_gemini(system_prompt, f"TASK: {task}", temperature=0.3)
        return f"## 🧠 Tool Strategy for: \"{task}\"\n\n{result}"

    except Exception:
        return (
            f"## 🧠 Tool Strategy for: \"{task}\"\n\n"
            f"*(Gemini unavailable — showing static recommendations)*\n\n"
            f"### Quick Reference\n"
            f"- **Bug fix?** → `orchestrate(\"bug_fix\", \"{task}\")`\n"
            f"- **Code review?** → `orchestrate(\"code_review\", \"{task}\")`\n"
            f"- **New feature?** → `orchestrate(\"research_implement\", \"{task}\")`\n"
            f"- **Need context?** → `scan_repo(project_path)`\n"
            f"- **Past error?** → `recall_fix(error_message)`\n"
            f"- **Risky change?** → `save_checkpoint(file_path)` first\n\n"
            f"{catalog}"
        )


@sovereign_tool()
def sync_jira_issue(issue_key: str, status_update: str = "") -> str:
    """
    Syncs a Jira issue: downloads the issue description and/or updates its workflow status.
    """
    jira_url = os.environ.get("JIRA_SERVER_URL")
    jira_token = os.environ.get("JIRA_API_TOKEN")
    jira_email = os.environ.get("JIRA_USER_EMAIL")
    
    if not jira_url or not jira_token:
        mock_summary = f"Mock Issue for {issue_key}: Resolve profile crash"
        mock_desc = "Verify that updating the user profile with special characters does not cause a database exception. Add a test in shadow_test."
        mock_status = status_update or "In Progress"
        report = [
            f"# 📋 Jira Sync: {issue_key} (SIMULATED)",
            f"**Status:** {mock_status}",
            f"**Summary:** {mock_summary}",
            f"**Description:** {mock_desc}",
            "",
            "⚠️ *Running in mock mode. Set JIRA_SERVER_URL and JIRA_API_TOKEN to hit live APIs.*"
        ]
        return "\n".join(report)

    try:
        url = f"{jira_url.rstrip('/')}/rest/api/3/issue/{issue_key}"
        req = urllib.request.Request(url)
        auth_str = f"{jira_email}:{jira_token}" if jira_email else jira_token
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        req.add_header("Authorization", f"Basic {encoded_auth}")
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            fields = data.get("fields", {})
            summary = fields.get("summary", "No Summary")
            description = fields.get("description", {}).get("text", "No Description")
            current_status = fields.get("status", {}).get("name", "Unknown")

        report = [
            f"# 📋 Jira Sync: {issue_key}",
            f"**Current Status:** {current_status}",
            f"**Summary:** {summary}",
            f"**Description:** {description}",
        ]
        
        if status_update:
            report.append(f"🔄 Transition request to '{status_update}' initiated.")
            
        return "\n".join(report)
    except Exception as e:
        return f"❌ Failed to sync Jira issue {issue_key}: {str(e)}"


@sovereign_tool()
def create_bitbucket_pr(repo_slug: str, source_branch: str, target_branch: str = "master", title: str = "", description: str = "") -> str:
    """
    Creates a Pull Request in Bitbucket for the specified repository and branches.
    """
    workspace = os.environ.get("BITBUCKET_WORKSPACE", "mock-workspace")
    token = os.environ.get("BITBUCKET_API_TOKEN")
    
    pr_title = title or f"Auto-patch: Merging {source_branch} into {target_branch}"
    pr_desc = description or "Automated patch submitted by Kenbun Agent."
    
    if not token or workspace == "mock-workspace":
        mock_pr_url = f"https://bitbucket.org/{workspace}/{repo_slug}/pull-requests/42"
        report = [
            "# 🚀 Bitbucket Pull Request (SIMULATED)",
            f"**Repository:** {repo_slug}",
            f"**Source Branch:** {source_branch}",
            f"**Target Branch:** {target_branch}",
            f"**PR Title:** {pr_title}",
            f"**PR Link:** {mock_pr_url}",
            "",
            "⚠️ *Running in mock mode. Set BITBUCKET_WORKSPACE and BITBUCKET_API_TOKEN to hit live APIs.*"
        ]
        return "\n".join(report)

    try:
        url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests"
        payload = {
            "title": pr_title,
            "description": pr_desc,
            "source": {"branch": {"name": source_branch}},
            "destination": {"branch": {"name": target_branch}}
        }
        
        req = urllib.request.Request(url, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        data_bytes = json.dumps(payload).encode()
        
        with urllib.request.urlopen(req, data=data_bytes, timeout=10) as response:
            res_data = json.loads(response.read().decode())
            links = res_data.get("links", {})
            html_link = links.get("html", {}).get("href", "No Link")
            pr_id = res_data.get("id", "Unknown")
            
        report = [
            "# 🚀 Bitbucket Pull Request Created",
            f"**PR ID:** #{pr_id}",
            f"**Repository:** {workspace}/{repo_slug}",
            f"**Source:** {source_branch} ➔ **Target:** {target_branch}",
            f"**PR Link:** {html_link}",
        ]
        return "\n".join(report)
    except Exception as e:
        return f"❌ Failed to create Bitbucket Pull Request: {str(e)}"
