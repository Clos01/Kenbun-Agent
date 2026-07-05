"""
🌸 Kenbun Slash-Command Registry (Hermes-parity)

Every /command is a small registered handler instead of a branch in a
1,200-line main(). The registry is the single source of truth for:
- dispatch (engine.py routes any '/x' input here)
- /help (generated, can never drift from reality)
- prompt completion (engine builds its completer from command_names())

Handlers receive a ShellContext and the raw argument string, and return
"exit" to close the REPL or None/"continue" to keep looping. Engine helpers
are imported lazily inside handlers to avoid a circular import (engine
imports this module).
"""
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class ShellContext:
    history: list
    llm_url: str
    llm_model: str
    pt_session: object = None


@dataclass
class CommandSpec:
    name: str
    handler: Callable
    description: str
    usage: str
    aliases: tuple = ()


_REGISTRY: dict = {}
_ORDERED: list = []


def command(name: str, description: str, usage: str = "", aliases: tuple = ()):
    def deco(fn):
        spec = CommandSpec(name=name, handler=fn, description=description,
                           usage=usage or name, aliases=aliases)
        _REGISTRY[name] = spec
        for alias in aliases:
            _REGISTRY[alias] = spec
        _ORDERED.append(spec)
        return fn
    return deco


def command_names() -> list:
    """All invocable names (commands + aliases) for the prompt completer."""
    return sorted(_REGISTRY.keys())


def dispatch(user_input: str, ctx: ShellContext) -> str:
    """Route a '/command args' line to its handler. Returns 'exit' or 'continue'."""
    from core.tools.cli import engine as eng
    parts = user_input.split(" ", 1)
    name = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    spec = _REGISTRY.get(name)
    if not spec:
        print(f"\n{eng.C_Y}❌ Unknown command: {name}. Type {eng.C_C}/help{eng.C_Y} for available commands.{eng.C_R}\n")
        return "continue"
    return spec.handler(ctx, args) or "continue"


def _panel(lines, title="", style="default"):
    """Route output through the Rich/skin renderer when available, ANSI otherwise."""
    from core.tools.cli import engine as eng
    if eng._ui:
        eng._ui.print_panel(lines, title=title, style=style)
    else:
        border = {"error": eng.C_RED, "warning": eng.C_Y, "success": eng.C_G,
                  "info": eng.C_C}.get(style, eng.C_P)
        eng.draw_box(lines, title=title, border_color=border, text_color=eng.C_W)


# ============================================================
# CORE SESSION COMMANDS
# ============================================================

@command("/help", "Show this guide", aliases=("/?",))
def _cmd_help(ctx, args):
    from core.tools.cli import engine as eng
    eng.log_event("❓ Displayed commands directory via /help")
    lines = []
    for spec in _ORDERED:
        alias = f" ({', '.join(spec.aliases)})" if spec.aliases else ""
        lines.append(f"  {eng.C_BOLD}{eng.C_C}{spec.usage}{eng.C_R}{eng.C_G}{alias}{eng.C_D} ➟ {spec.description}{eng.C_R}")
    yolo_status = (
        f"{eng.C_RED}⚡ YOLO MODE: ON  — Commands execute automatically!{eng.C_R}"
        if eng.YOLO_MODE else
        f"{eng.C_D}  YOLO MODE: off — Commands need your approval{eng.C_R}"
    )
    print()
    _panel(lines + ["", yolo_status], title=f"🌸 {eng.C_Y}KENBUN COMMANDS")
    print()


@command("/exit", "Gracefully close session")
def _cmd_exit(ctx, args):
    from core.tools.cli import engine as eng
    print(f"\n{eng.C_P}🌸 Sayonara! Terminating agent session...{eng.C_R}\n")
    eng.log_event("🌸 Termchat Session Terminated cleanly via /exit")
    eng.save_clean_exit_reflection(ctx.history)
    if eng.active_brain_health_dir:
        backup_path = Path(eng.active_brain_health_dir) / "active_session_backup.json"
        if backup_path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass
    return "exit"


@command("/reset", "Clear dialogue history")
def _cmd_reset(ctx, args):
    from core.tools.cli import engine as eng
    eng.log_event("🧹 Dialogue history purged via /reset")
    del ctx.history[1:]  # in place — engine holds the same list object
    eng.save_session_backup(ctx.history, Path.cwd(), ctx.llm_url, ctx.llm_model)
    print(f"\n{eng.C_Y}🧹 Dialogue history purged.{eng.C_R}\n")


@command("/system", "Show environment config")
def _cmd_system(ctx, args):
    from core.tools.cli import engine as eng
    eng.log_event("⚙️ Dumped environment parameters via /system")
    fresh_env = eng.load_env_vars()
    cols = eng.get_columns()
    print(f"\n{eng.C_G}🏛  Active Configuration Check:{eng.C_R}")
    for k, v in fresh_env.items():
        if "KEY" in k or "SECRET" in k or "TOKEN" in k:
            v = "******** (Masked Securely)"
        else:
            v = eng.scrub_secrets(v)
        prefix = f"  • {eng.C_C}{k:<24}{eng.C_R}= "
        pref_len = eng.visible_len(prefix)
        wrapped_lines = eng.clean_wrap_text(v, cols - pref_len - 2).splitlines()
        if wrapped_lines:
            print(f"{prefix}{wrapped_lines[0]}")
            for wl in wrapped_lines[1:]:
                print(f"{' ' * pref_len}{wl}")
        else:
            print(prefix)
    print()


@command("/skin", "Change CLI skin theme", usage="/skin [name]")
def _cmd_skin(ctx, args):
    from core.tools.cli import engine as eng
    if not eng._ui:
        print(f"\n{eng.C_Y}⚠️ Skin system is only available when Rich is installed.{eng.C_R}\n")
        return
    if args:
        print(f"\n{eng._ui.switch_skin(args)}\n")
    else:
        _panel(eng._ui.list_skins_table().split("\n"), title="🎨 active skin")
        print()


@command("/yolo", "Toggle YOLO mode (auto-approve commands)")
def _cmd_yolo(ctx, args):
    from core.tools.cli import engine as eng
    eng.YOLO_MODE = not eng.YOLO_MODE
    if eng.YOLO_MODE:
        _panel([
            f"{eng.C_RED}{eng.C_BOLD}⚡ YOLO MODE ACTIVATED ⚡{eng.C_R}",
            "",
            "Commands proposed by Kenbun will execute automatically.",
            "Nuclear commands (rm -rf /, mkfs, dd, fork bombs)",
            "are ALWAYS blocked regardless of this setting.",
            "",
            f"Type {eng.C_C}/yolo{eng.C_RED} again to return to safe mode.",
        ], title=f"{eng.C_RED}⚡ YOLO MODE ON", style="error")
    else:
        print(f"\n{eng.C_G}✓ YOLO mode OFF. Manual approval restored.{eng.C_R}\n")


# ============================================================
# MEMORY & KNOWLEDGE COMMANDS
# ============================================================

@command("/search", "Search UI/UX design database", usage="/search <topic>")
def _cmd_search(ctx, args):
    from core.tools.cli import engine as eng
    if not args:
        print(f"\n{eng.C_Y}⚠️ Usage: /search <design topic / style / palette>{eng.C_R}\n")
        return
    eng.log_event(f"🔍 Direct UI-UX Pro Max search query: {args}")
    print(f"\n{eng.C_G}🔍 Searching UI-UX Pro Max database for: '{args}'...{eng.C_R}")
    res = eng.get_design_suggestions(args)
    if res:
        cols = eng.get_columns()
        print(f"\n{eng.C_W}{eng.clean_wrap_text(res, cols - 2)}{eng.C_R}\n")
    else:
        print(f"\n{eng.C_Y}❌ No matches or search scripts found.{eng.C_R}\n")


@command("/remember", "Save a note to Hivemind", usage="/remember <title> = <content>")
def _cmd_remember(ctx, args):
    from core.tools.cli import engine as eng
    if "=" not in args:
        print(f"\n{eng.C_Y}⚠️ Usage: /remember <title> = <content>{eng.C_R}\n")
        return
    title, content = (part.strip() for part in args.split("=", 1))
    if not title or not content:
        print(f"\n{eng.C_Y}⚠️ Usage: /remember <title> = <content>{eng.C_R}\n")
        return
    eng.log_event(f"🧠 Saving memory rule: '{title}'")
    print(f"\n{eng.C_G}🧠 Saving memory to Hivemind: '{title}'...{eng.C_R}")
    res = eng.save_concept_to_hivemind(title, content, tags="user-memories", category="concepts")
    print(f"\n{eng.C_W}{res}{eng.C_R}\n")


@command("/recall", "Search Hivemind memories", usage="/recall <query>")
def _cmd_recall(ctx, args):
    from core.tools.cli import engine as eng
    if not args:
        print(f"\n{eng.C_Y}⚠️ Usage: /recall <query>{eng.C_R}\n")
        return
    print(f"\n{eng.C_G}🔍 Searching Hivemind semantically for: '{args}'...{eng.C_R}")
    res = eng.search_hivemind(args, category="concepts")
    try:
        results = json.loads(res)
    except Exception:
        results = []

    if isinstance(results, dict) and "error" in results:
        _panel([f"❌ {results['error']}"], title="🌸 HIVE RECALL ERROR", style="error")
    elif not results or not isinstance(results, list):
        if isinstance(res, str) and res.startswith("ERROR"):
            _panel([f"❌ {res}"], title="🌸 HIVE RECALL ERROR", style="error")
        else:
            _panel(["No matching memories found in the Hivemind."], title="🌸 HIVE RECALL (0 Results)")
    elif len(results) == 1 and "error" in results[0]:
        _panel([f"❌ {results[0]['error']}"], title="🌸 HIVE RECALL ERROR", style="error")
    else:
        box_lines = []
        for idx, item in enumerate(results, 1):
            box_lines.append(f"{eng.C_Y}[{idx}] {item.get('title', 'Untitled')} (ID: {item.get('id', 'N/A')}){eng.C_R}")
            if item.get("tags"):
                box_lines.append(f"{eng.C_D}Tags: {item['tags']}{eng.C_R}")
            for line in item.get("content", "").splitlines():
                box_lines.append(f"  {line}")
            if idx < len(results):
                box_lines.append("---")
        _panel(box_lines, title=f"🌸 HIVE RECALL Results ({len(results)})")
    print()


# ============================================================
# TOOL & SKILL COMMANDS
# ============================================================

BUILTIN_TOOLS = [
    {"name": "scan_repo", "module": "core.tools.memory.repo_mapper", "purpose": "Scans files and builds workspace maps."},
    {"name": "review_code_with_gemini", "module": "core.tools.audit.gemini_reviewer", "purpose": "Deep Cloud AI code review with validation."},
    {"name": "research_with_gemini", "module": "core.tools.audit.gemini_reviewer", "purpose": "Broad-context technical and pricing research."},
    {"name": "consult_supervisor", "module": "core.tools.audit.supervisor_agent", "purpose": "Run System 2 architecture and compliance checks."},
    {"name": "remember_fix", "module": "core.tools.utils.error_memory", "purpose": "Save post-mortems and resolved bugs to ChromaDB."},
    {"name": "recall_fix", "module": "core.tools.utils.error_memory", "purpose": "Search local fallback or Hivemind database for historical fixes."},
    {"name": "save_checkpoint", "module": "core.tools.utils.backtracker", "purpose": "Saves git/file state before running experimental edits."},
    {"name": "restore_checkpoint", "module": "core.tools.utils.backtracker", "purpose": "Restores files to a saved checkpoint if validation fails."},
    {"name": "run_code_safely", "module": "core.tools.execution.sandbox_runner", "purpose": "Safe sandboxed execution of terminal commands."},
    {"name": "reflect_and_distill", "module": "core.tools.audit.reflection_agent", "purpose": "Reflects on step performance and creates post-mortems."},
    {"name": "guardrail_audit", "module": "core.tools.audit.guardrail_agent", "purpose": "Dynamic check for prompt injection and token limits."},
    {"name": "maze_verification", "module": "core.tools.utils.maze_protocol", "purpose": "Verifies system properties and backtracks if regression is found."},
    {"name": "tune_assembly", "module": "core.tools.utils.bayesian", "purpose": "Tunes agent weights based on historical success rates."},
    {"name": "consult_hivemind", "module": "core.tools.audit.consult_architect", "purpose": "Consults the knowledge base for architectural patterns."},
    {"name": "generate_discovery_form", "module": "core.tools.audit.discovery_agent", "purpose": "Creates form schema for user/UI requirement gathering."},
    {"name": "autofix_linter", "module": "core.tools.audit.linter_autofix", "purpose": "Autonomic linter fixing of syntax/formatting errors."},
]

# Public tool name -> actual function name inside its module
_TOOL_FUNC_ALIASES = {
    "consult_supervisor": "run_supervisor_audit",
    "review_code_with_gemini": "gemini_code_review",
    "research_with_gemini": "gemini_research",
    "reflect_and_distill": "_reflect_and_distill",
    "guardrail_audit": "run_guardrail_audit",
    "maze_verification": "backward_verify",
    "consult_hivemind": "consult_brain",
}


@command("/tools", "List or inspect harvested sovereign tools", usage="/tools [name]")
def _cmd_tools(ctx, args):
    from core.tools.cli import engine as eng
    if not args:
        tool_lines = [
            f"{eng.C_Y}{'Tool Name':<25}  {'Python Module Reference':<36}  {'Purpose':<50}{eng.C_R}",
            f"{eng.C_D}" + "─" * 115 + f"{eng.C_R}",
        ]
        for t in BUILTIN_TOOLS:
            tool_lines.append(
                f"{eng.C_G}{t['name']:<25}{eng.C_R}  {eng.C_W}{t['module']:<36}{eng.C_R}  {eng.C_D}{t['purpose']}{eng.C_R}"
            )
        harvested = eng.get_harvested_tools()
        if harvested:
            tool_lines.append("")
            tool_lines.append(f"{eng.C_Y}Harvested Sovereign Tools:{eng.C_R}")
            tool_lines.append(f"{eng.C_D}" + "─" * 115 + f"{eng.C_R}")
            for t_name, entry in sorted(harvested.items()):
                desc = entry.description.splitlines()[0][:50] if entry.description else "No description."
                module_ref = getattr(entry.handler, "__module__", "dynamic")
                tool_lines.append(
                    f"{eng.C_G}{entry.name:<25}{eng.C_R}  {eng.C_W}{module_ref:<36}{eng.C_R}  {eng.C_D}{desc}{eng.C_R}"
                )
        _panel(tool_lines, title="🌸 ACTIVE ASSEMBLY TOOLS & ORCHESTRATORS")
        print(f"\n  Use {eng.C_C}/tools <tool_name>{eng.C_R} for details or {eng.C_C}/run <tool_name> arg=val{eng.C_R} to execute.\n")
        return

    target_tool = args.split(" ", 1)[0]
    b_tool = next((t for t in BUILTIN_TOOLS if t["name"] == target_tool), None)
    if b_tool:
        handler = None
        try:
            import importlib
            mod = importlib.import_module(b_tool["module"])
            handler = getattr(mod, _TOOL_FUNC_ALIASES.get(b_tool["name"], b_tool["name"]))
        except Exception:
            pass
        sig_str = "(...)"
        if handler:
            import inspect
            try:
                sig_str = f"{b_tool['name']}{inspect.signature(handler)}"
            except Exception:
                pass
        _panel([
            f"{eng.C_Y}Name:{eng.C_R}        {eng.C_G}{b_tool['name']}{eng.C_R}",
            f"{eng.C_Y}Module:{eng.C_R}      {b_tool['module']}",
            f"{eng.C_Y}Signature:{eng.C_R}   {sig_str}",
            "---",
            f"{eng.C_Y}Purpose:{eng.C_R}",
            f"  {b_tool['purpose']}",
        ], title=f"🌸 TOOL: {b_tool['name'].upper()}")
        print()
        return

    harvested = eng.get_harvested_tools()
    entry = harvested.get(target_tool)
    if not entry:
        print(f"\n{eng.C_Y}❌ Tool '{target_tool}' not found.{eng.C_R}\n")
        return
    import inspect
    sig = inspect.signature(entry.handler)
    details = [
        f"{eng.C_Y}Name:{eng.C_R}        {eng.C_G}{entry.name}{eng.C_R}",
        f"{eng.C_Y}Category:{eng.C_R}    {entry.category}",
        f"{eng.C_Y}Signature:{eng.C_R}   {entry.name}{sig}",
        f"{eng.C_Y}Async:{eng.C_R}       {entry.is_async}",
        f"{eng.C_Y}Required Env:{eng.C_R} {', '.join(entry.requires_env) if entry.requires_env else 'None'}",
        "---",
        f"{eng.C_Y}Description:{eng.C_R}",
    ]
    details.extend(f"  {line}" for line in entry.description.splitlines())
    _panel(details, title=f"🌸 TOOL: {entry.name.upper()}")
    print()


@command("/skills", "List or inspect design & template skills", usage="/skills [name]")
def _cmd_skills(ctx, args):
    from core.tools.cli import engine as eng
    skills = eng.get_harvested_skills()
    if not args:
        if not skills:
            print(f"\n{eng.C_D}  No harvested template skills active.{eng.C_R}\n")
            return
        skill_lines = []
        for s_name, s_data in sorted(skills.items()):
            desc_line = s_data["description"].splitlines()[0][:60]
            skill_lines.append(f"  • {eng.C_G}{s_name:<25}{eng.C_R}{eng.C_D}➟ {desc_line}{eng.C_R}")
        _panel(skill_lines, title=f"🌸 ACTIVE DESIGN SKILLS ({len(skills)})")
        print(f"\n  Use {eng.C_C}/skills <skill_name>{eng.C_R} to inspect the full design workflow.\n")
        return

    s_data = skills.get(args.split(" ", 1)[0])
    if not s_data:
        print(f"\n{eng.C_Y}❌ Skill '{args}' not found.{eng.C_R}\n")
        return
    details = [
        f"{eng.C_Y}Name:{eng.C_R}        {eng.C_G}{s_data['name']}{eng.C_R}",
        f"{eng.C_Y}Path:{eng.C_R}        {s_data['path']}",
        f"{eng.C_Y}Triggers:{eng.C_R}    {', '.join(s_data['triggers']) if s_data['triggers'] else 'None'}",
        "---",
        f"{eng.C_Y}SKILL BLUEPRINT & INSTRUCTIONS:{eng.C_R}",
    ]
    details.extend(f"  {line}" for line in s_data["content"].splitlines())
    _panel(details, title=f"🌸 SKILL: {s_data['name'].upper()}")
    print()


@command("/stats", "Dump Bayesian & Hivemind governance metrics")
def _cmd_stats(ctx, args):
    from core.tools.cli import engine as eng
    try:
        from core.tools.utils.bayesian import get_confidence
        print(f"\n{eng.C_G}📊 SYSTEM 3 GOVERNANCE & BAYESIAN METRICS{eng.C_R}")
        stats = [
            f"  {eng.C_C}Tool Executions{eng.C_R}",
            f"  • consult_supervisor (Security): {get_confidence('consult_supervisor', 'security'):.2f}%",
            f"  • review_code_with_gemini: {get_confidence('review_code_with_gemini', 'code_review'):.2f}%",
            f"  • research_official_docs: {get_confidence('research_official_docs', 'research'):.2f}%",
            f"  • scan_repo (Codebase): {get_confidence('scan_repo', 'codebase'):.2f}%",
        ]
        _panel(stats, title="🌸 METRICS")
        print()
    except Exception as e:
        print(f"\n{eng.C_Y}⚠️ Unable to fetch Bayesian metrics: {e}{eng.C_R}\n")


@command("/run", "Live REPL execution of a harvested tool", usage="/run <tool> [args]")
def _cmd_run(ctx, args):
    from core.tools.cli import engine as eng
    if not args:
        print(f"\n{eng.C_Y}⚠️ Usage: /run <tool_name> [param1=val1 param2=val2 ...]{eng.C_R}\n")
        return
    run_parts = args.split(" ", 1)
    tool_name = run_parts[0]
    tools = eng.get_harvested_tools()
    entry = tools.get(tool_name)
    if not entry:
        print(f"\n{eng.C_Y}❌ Tool '{tool_name}' not found.{eng.C_R}\n")
        return

    kwargs, pos_args = {}, []
    if len(run_parts) > 1:
        for token in re.findall(r'[^\s"]+|"[^"]*"', run_parts[1].strip()):
            if "=" in token:
                k, v = token.split("=", 1)
                kwargs[k] = v.strip('"')
            else:
                pos_args.append(token.strip('"'))

    missing_envs = [ev for ev in entry.requires_env if not os.environ.get(ev)]
    if missing_envs:
        print(f"\n{eng.C_RED}❌ Missing required environment variables: {', '.join(missing_envs)}{eng.C_R}\n")
        return

    print(f"\n{eng.C_G}🚀 Executing tool '{tool_name}' with args={pos_args} kwargs={kwargs}...{eng.C_R}")
    eng.log_event(f"🚀 Manual REPL run of tool '{tool_name}': args={pos_args}, kwargs={kwargs}")
    try:
        if entry.is_async:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    result = asyncio.run_coroutine_threadsafe(entry.handler(*pos_args, **kwargs), loop).result()
                else:
                    result = loop.run_until_complete(entry.handler(*pos_args, **kwargs))
            except RuntimeError:
                result = asyncio.run(entry.handler(*pos_args, **kwargs))
        else:
            result = entry.handler(*pos_args, **kwargs)
        print(f"\n{eng.C_G}✓ Result:{eng.C_R}")
        print(json.dumps(result, indent=2) if isinstance(result, (dict, list)) else result)
        print()
    except Exception as e:
        print(f"\n{eng.C_RED}❌ Tool execution failed: {e}{eng.C_R}\n")


# ============================================================
# BACKGROUND AGENT COMMANDS
# ============================================================

@command("/spawn", "Run command in background agent", usage="/spawn <cmd>")
def _cmd_spawn(ctx, args):
    from core.tools.cli import engine as eng
    if eng.spawn_agent is None:
        print(f"\n{eng.C_Y}⚠️ Sub-agent bus not available.{eng.C_R}\n")
        return
    if not args:
        print(f"\n{eng.C_Y}Usage: /spawn <shell command>{eng.C_R}\n")
        return
    task_name = args[:40]
    aid = eng.spawn_agent(task_name, args)
    print(f"\n{eng.C_G}🟡 Agent spawned:{eng.C_R} [{aid}] {task_name}")
    print(f"  Use {eng.C_C}/agents{eng.C_R} to check status.\n")


@command("/agents", "List all running background agents", aliases=("/tasks",))
def _cmd_agents(ctx, args):
    from core.tools.cli import engine as eng
    if eng.list_agents is None:
        print(f"\n{eng.C_Y}⚠️ Sub-agent bus not available.{eng.C_R}\n")
        return
    agents = eng.list_agents()
    if not agents:
        print(f"\n{eng.C_D}  No active agents.{eng.C_R}\n")
        return
    agent_lines = []
    for a in agents:
        icon = {"RUNNING": "🟡", "DONE": "✅", "ERROR": "❌", "KILLED": "🛑"}.get(a["status"], "⚪")
        agent_lines.append(f"  {icon} [{a['id']}] {a['task']}  ({a['status']})")
        if a.get("error") and a["status"] in ("ERROR", "TIMEOUT"):
            agent_lines.append(f"     Error: {a['error'][:80]}")
    _panel(agent_lines, title=f"🤖 {eng.C_Y}ACTIVE AGENTS", style="success")
    print()


@command("/kill", "Kill a background agent", usage="/kill <id>")
def _cmd_kill(ctx, args):
    from core.tools.cli import engine as eng
    if eng.kill_agent is None:
        print(f"\n{eng.C_Y}⚠️ Sub-agent bus not available.{eng.C_R}\n")
        return
    if not args:
        print(f"\n{eng.C_Y}Usage: /kill <agent-id>{eng.C_R}\n")
        return
    ok = eng.kill_agent(args.split(" ", 1)[0])
    print(f"\n{'🛑 Killed: ' if ok else '⚠️ Not found: '}{args}\n")
