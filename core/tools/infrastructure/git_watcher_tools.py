import os
import json
import urllib.request
import urllib.error
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from tools.registry import sovereign_tool
from tools.infrastructure.config import settings
from tools.audit.gemini_reviewer import call_gemini_pro
from tools.utils.backtracker import save_checkpoint
from tools.audit.linter_autofix import _resolve_paths

logger = logging.getLogger("git_watcher_tools")

def _parse_github_repo(repo_url: str) -> Optional[tuple[str, str]]:
    """
    Parses a GitHub repo URL or 'owner/repo' format into (owner, repo).
    Supports HTTPS, SSH, and raw formats.
    """
    repo_url = repo_url.strip()
    match = re.search(r"(?:github\.com/|git@github\.com:)([^/]+)/([^/.]+)(?:\.git)?", repo_url)
    if match:
        return match.group(1), match.group(2)
    parts = repo_url.split('/')
    if len(parts) == 2:
        return parts[0], parts[1]
    return None

def _make_github_request(url: str, token: Optional[str], accept: str, ssl_context) -> Any:
    """Performs GitHub API requests, falling back to unauthenticated if token fails with 401/403."""
    req = urllib.request.Request(url)
    req.add_header("Accept", accept)
    req.add_header("User-Agent", "Kenbun-Agent/1.0")
    if token and token.strip() and not token.strip().startswith("your_"):
        req.add_header("Authorization", f"token {token}")
        
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as he:
        if he.code in (401, 403) and token:
            logger.warning(f"GitHub request returned {he.code} with token. Retrying without token.")
            retry_req = urllib.request.Request(url)
            retry_req.add_header("Accept", accept)
            retry_req.add_header("User-Agent", "Kenbun-Agent/1.0")
            with urllib.request.urlopen(retry_req, timeout=10, context=ssl_context) as response:
                return json.loads(response.read().decode())
        raise

@sovereign_tool(name="fetch_git_pushes")
def fetch_git_pushes(repo_url: str, branch: str = "main") -> str:
    """
    Fetches the latest Git commits/pushes from a specified GitHub repository.
    Compares against the last processed commit SHA stored in git_watcher_state.json.
    Returns a JSON string containing the list of new commits, messages, and raw file patches.
    """
    repo_info = _parse_github_repo(repo_url)
    if not repo_info:
        return json.dumps({"status": "error", "message": f"Invalid GitHub repository format: '{repo_url}'"}, indent=2)

    owner, repo = repo_info
    repo_key = f"{owner}/{repo}"

    # Load last processed commit SHA
    state_file = settings.GIT_WATCH_STATE_FILE
    last_sha = None
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                last_sha = state.get(repo_key)
        except Exception as e:
            logger.warning(f"Failed to read state file: {e}")

    # Set up GitHub API request
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?sha={branch}"
    token = os.environ.get("GITHUB_TOKEN") or (settings.GITHUB_TOKEN if hasattr(settings, "GITHUB_TOKEN") else None)

    import ssl
    try:
        ssl_context = ssl._create_unverified_context()
    except AttributeError:
        ssl_context = None

    try:
        commits_list = _make_github_request(url, token, "application/vnd.github.v3+json", ssl_context)
    except urllib.error.HTTPError as he:
        if he.code == 403 and "rate limit" in str(he.reason).lower():
            return json.dumps({"status": "error", "message": "GitHub API rate limit exceeded. Set GITHUB_TOKEN in your .env file."}, indent=2)
        return json.dumps({"status": "error", "message": f"GitHub API HTTP Error {he.code}: {he.reason}"}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Failed to fetch commits from {repo_url}: {str(e)}"}, indent=2)

    if not isinstance(commits_list, list) or not commits_list:
        return json.dumps({"status": "no_commits", "message": f"No commits found on branch {branch}."}, indent=2)

    # If this is the first run (no last processed SHA), save the latest one and exit
    if not last_sha:
        latest_sha = commits_list[0]["sha"]
        # Write state immediately so we don't process history
        try:
            state = {}
            if state_file.exists():
                with open(state_file, "r") as f:
                    state = json.load(f)
            state[repo_key] = latest_sha
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to initialize state file: {e}")
            
        return json.dumps({
            "status": "initialized",
            "message": f"Initialized tracking for {repo_key} at latest SHA: {latest_sha[:8]}. Watching for future pushes.",
            "latest_sha": latest_sha
        }, indent=2)

    # Find the commits that occurred after the last processed SHA (reverse list to process oldest -> newest)
    new_commits = []
    found_last = False
    for commit in commits_list:
        if commit["sha"] == last_sha:
            found_last = True
            break
        new_commits.append(commit)

    # If the last seen SHA was not found in the recent list, it might have been force-pushed away.
    # In that case, we fallback to processing just the single latest commit to be safe.
    if not found_last and new_commits:
        logger.warning(f"Last processed SHA {last_sha[:8]} not found in history of {repo_key}. Processing only the latest commit.")
        new_commits = [new_commits[0]]

    if not new_commits:
        return json.dumps({
            "status": "no_new_pushes",
            "message": f"No new pushes detected for {repo_key}. Already up to date at SHA {last_sha[:8]}.",
            "last_sha": last_sha
        }, indent=2)

    # Reverse to process oldest -> newest
    new_commits.reverse()

    # Limit to maximum of 3 commits per cycle to avoid token limit issues and keep it controlled
    new_commits = new_commits[:3]

    processed_commits = []
    for commit in new_commits:
        sha = commit["sha"]
        message = commit["commit"]["message"]
        author = commit["commit"]["author"]["name"]
        
        commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
        files_data = []
        try:
            detail = _make_github_request(commit_url, token, "application/vnd.github.v3+json", ssl_context)
            for file_entry in detail.get("files", []):
                files_data.append({
                    "filename": file_entry.get("filename"),
                    "status": file_entry.get("status"),
                    "patch": file_entry.get("patch")  # contains raw diff patch
                })
        except Exception as e:
            logger.error(f"Failed to fetch details for commit {sha[:8]}: {e}")
            # Continue processing, but without file diffs
            pass

        processed_commits.append({
            "sha": sha,
            "message": message,
            "author": author,
            "files": files_data
        })

    return json.dumps({
        "status": "new_pushes",
        "repo": repo_key,
        "commits": processed_commits,
        "latest_sha": new_commits[-1]["sha"]
    }, indent=2)

@sovereign_tool(name="analyze_push_changes")
def analyze_push_changes(repo_url: str, commit_data: str, project_path: str = ".") -> str:
    """
    Analyzes the git push changes (commits & diffs) from a watched repository (like hermes-agent)
    and designs code modifications to port those changes or ideas into Kenbun.
    Outputs a JSON array of file operations: [{"file_path": "...", "content": "...", "action": "create|modify"}].
    """
    try:
        data = json.loads(commit_data)
    except Exception:
        return json.dumps({"status": "error", "message": "Failed to parse commit data JSON."}, indent=2)

    status = data.get("status")
    if status in ("no_new_pushes", "initialized", "no_commits", "error"):
        return json.dumps({"status": "skip", "message": f"Skipping analysis. Reason: {data.get('message', 'No new commits.')}"}, indent=2)

    commits = data.get("commits", [])
    if not commits:
        return json.dumps({"status": "skip", "message": "No new commits to analyze."}, indent=2)

    # Synthesize description of the commits and diffs
    commit_summaries = []
    for c in commits:
        summary = f"Commit {c['sha'][:8]} by {c['author']}:\nMessage: {c['message']}\nChanges:"
        for f in c.get("files", []):
            summary += f"\n- File: {f['filename']} ({f['status']})\nPatch:\n{f['patch'] or 'No patch available.'}\n"
        commit_summaries.append(summary)

    all_commits_str = "\n=======================\n".join(commit_summaries)

    # Let's perform a lightweight repo scan so the model knows Kenbun's current layout
    from tools.memory.repo_mapper import scan_repo
    repo_map = scan_repo(project_path=str(settings.PROJECT_ROOT))

    system_prompt = (
        "You are the Kenbun Autonomic Integrator. Your goal is to keep Kenbun highly sophisticated, "
        "incorporating state-of-the-art agent engineering paradigms from Hermes Agent (nousresearch/hermes-agent) "
        "and other advanced systems.\n\n"
        "Analyze the provided git commit pushes and determine if they contain useful ideas, features, patterns, "
        "prompts, or fixes that should be ported to Kenbun. Draft corresponding changes for Kenbun.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. You must output ONLY a valid JSON array of file operations with no extra text or markdown formatting.\n"
        "2. The JSON array must look like this:\n"
        "[\n"
        "  {\n"
        "    \"file_path\": \"core/tools/some_file.py\",\n"
        "    \"content\": \"...full new or updated code content...\",\n"
        "    \"action\": \"create\" or \"modify\"\n"
        "  }\n"
        "]\n"
        "3. Ensure the file paths are relative to Kenbun's project root (e.g. starting with 'core/tools/...').\n"
        "4. Do NOT output markdown ticks (e.g. ```json) around your response. Output only the raw JSON.\n"
        "5. If no changes are needed, output an empty JSON array: `[]`."
    )

    user_message = (
        f"Kenbun Codebase Layout:\n{repo_map}\n\n"
        f"Git commits & diffs pushed to {repo_url}:\n{all_commits_str}"
    )

    # Call LLM to design the integration
    response = call_gemini_pro(f"{system_prompt}\n\nUser Content:\n{user_message}")

    # Robust JSON extraction
    response_clean = response.strip()
    if response_clean.startswith("```"):
        # Strip code blocks if LLM disobeyed instructions
        response_clean = re.sub(r"^```[a-zA-Z]*\n", "", response_clean)
        response_clean = re.sub(r"\n```$", "", response_clean)
        response_clean = response_clean.strip()

    try:
        # Verify it parses as JSON
        json_data = json.loads(response_clean)
        if not isinstance(json_data, list):
            raise ValueError("Response is not a list/array.")
        return json.dumps({
            "status": "success",
            "changes": json_data,
            "latest_sha": data.get("latest_sha"),
            "repo": data.get("repo")
        }, indent=2)
    except Exception as je:
        logger.error(f"Failed to parse LLM integration proposal: {je}. Raw output was:\n{response}")
        return json.dumps({
            "status": "error",
            "message": f"LLM output could not be parsed as a JSON array: {str(je)}",
            "raw_response": response
        }, indent=2)

@sovereign_tool(name="apply_git_patch")
def apply_git_patch(changes_json: str) -> str:
    """
    Safely applies filesystem changes (file creations and modifications) proposed by the integration analysis.
    Saves recovery checkpoints for all modified files first, and performs strict path boundary validation.
    Returns a formatted markdown report.
    """
    try:
        data = json.loads(changes_json)
    except Exception:
        return "❌ Error: Failed to parse integration changes JSON."

    status = data.get("status")
    if status == "skip":
        return f"⏭️ Skipped: {data.get('message')}"
    if status == "error":
        return f"❌ Error: {data.get('message')}"

    changes = data.get("changes", [])
    if not changes:
        return "✅ No changes to apply. Kenbun is already aligned or the push contained no relevant upgrades."

    applied_files = []
    errors = []

    # Apply changes
    for change in changes:
        file_path = change.get("file_path")
        content = change.get("content")
        action = change.get("action")

        if not file_path or content is None:
            errors.append(f"Invalid change entry: {change}")
            continue

        try:
            # Enforce path containment
            resolved_file, resolved_proj = _resolve_paths(file_path, settings.PROJECT_ROOT)
            
            # Save backup checkpoint if file already exists
            if resolved_file.exists():
                print(f"🔄 Saving checkpoint for '{resolved_file.name}' before git integration...")
                save_checkpoint(str(resolved_file), label="pre_git_integration")

            # Ensure parent directories exist
            resolved_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the file
            resolved_file.write_text(content, encoding="utf-8")
            
            # Format and lint immediately
            try:
                from tools.audit.linter_autofix import autofix_linter
                autofix_linter(str(resolved_file), str(settings.PROJECT_ROOT))
            except Exception as le:
                logger.warning(f"Linter auto-fix failed on {file_path}: {le}")

            applied_files.append(f"- **{action.upper()}**: [`{file_path}`](file://{resolved_file})")
            
        except Exception as ex:
            errors.append(f"Failed to apply {file_path}: {ex}")

    # Build report
    report = [
        "## 🛠️ Git Push Integration: File Operations Applied",
        f"**Status:** {'Success with Warnings' if errors else 'Success'}",
        ""
    ]
    if applied_files:
        report.append("### Changes Applied:")
        report.extend(applied_files)
        report.append("")
    if errors:
        report.append("### Warnings/Errors:")
        for err in errors:
            report.append(f"- ⚠️ {err}")
        report.append("")
    else:
        # Atomic commit SHA state updates on success
        latest_sha = data.get("latest_sha")
        repo_key = data.get("repo")
        if latest_sha and repo_key:
            try:
                state_file = settings.GIT_WATCH_STATE_FILE
                state = {}
                if state_file.exists():
                    with open(state_file, "r") as f:
                        state = json.load(f)
                state[repo_key] = latest_sha
                state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(state_file, "w") as f:
                    json.dump(state, f, indent=4)
                report.append(f"💾 **State Saved:** Updated SHA checkpoint for `{repo_key}` to `{latest_sha[:8]}`.")
            except Exception as se:
                report.append(f"⚠️ **State Save Failed:** Could not update SHA state: {se}")

    return "\n".join(report)
