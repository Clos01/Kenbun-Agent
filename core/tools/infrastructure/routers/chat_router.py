import os
import re
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from core.tools.infrastructure.config import settings
from core.tools.strategy.token_governor import token_governor
from core.tools.execution.claude_code_agent import claude_code_agent
from core.tools.execution.p330_worker import p330_worker

router = APIRouter()
project_root = settings.PROJECT_ROOT
TASKS_FILE = project_root / "brain_health" / "swarm_tasks.json"

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to Hermes")

class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field("New Transmissions", description="Initial title of the session")

class ChatSessionMessageRequest(BaseModel):
    message: str = Field(..., description="The user message to send")

def execute_cli_command(command: str) -> str:
    """
    Safely executes a whitelisted CLI command on the user's hardware.
    Protected by the absolute regex whitelist and YOLO filters of terminal_chat.py.
    """
    import sys
    import subprocess
    
    try:
        scripts_dir = Path("/app/scripts")
        if not scripts_dir.exists():
            scripts_dir = Path(settings.PROJECT_ROOT) / "scripts"
            
        from scripts.terminal_chat import is_yolo_safe
    except Exception as e:
        return f"❌ Internal Error: Failed to load CLI security engine: {e}"
        
    if not is_yolo_safe(command):
        return "❌ Security Violation: Command is blocked by yolo sandboxing rules."
        
    try:
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(settings.PROJECT_ROOT),
            timeout=30.0
        )
        output = res.stdout
        if res.stderr:
            output += f"\n{res.stderr}"
        if not output.strip():
            output = f"Command completed with exit code {res.returncode}."
        return f"```\n{output}\n```"
    except subprocess.TimeoutExpired:
        return "❌ Error: Command execution timed out after 30 seconds."
    except Exception as e:
        return f"❌ Error: Command execution failed: {e}"


@router.get("/api/v1/chat/sessions")
async def get_chat_sessions():
    """Lists summaries of all active chat sessions."""
    from core.tools.utils import chat_history_manager
    return chat_history_manager.list_sessions()

@router.post("/api/v1/chat/sessions")
async def create_chat_session(req: Optional[CreateSessionRequest] = None):
    """Creates a new empty chat session."""
    from core.tools.utils import chat_history_manager
    title = req.title if req and req.title else "New Transmissions"
    return chat_history_manager.create_session(title=title)

@router.get("/api/v1/chat/sessions/{session_id}")
async def get_chat_session(session_id: str):
    """Retrieves a single chat session with its full message history."""
    from core.tools.utils import chat_history_manager
    session = chat_history_manager.get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": f"Session {session_id} not found"})
    return session

@router.delete("/api/v1/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Deletes a chat session by ID."""
    from core.tools.utils import chat_history_manager
    success = chat_history_manager.delete_session(session_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": f"Session {session_id} not found"})
    return {"status": "success", "message": f"Session {session_id} deleted"}

@router.post("/api/v1/chat/sessions/{session_id}/message")
async def post_message_to_session(session_id: str, req: ChatSessionMessageRequest):
    """Sends a message within an existing chat session and queries the AI using history context."""
    from core.tools.utils import chat_history_manager
    from core.tools.utils.llm_router import call_llm_gateway
    
    session = chat_history_manager.get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": f"Session {session_id} not found"})
        
    user_msg = chat_history_manager.add_message_to_session(session_id, "user", req.message)
    
    msg_strip = req.message.strip()
    if msg_strip.startswith("/run ") or msg_strip.startswith("run: "):
        command = msg_strip[5:] if msg_strip.startswith("/run ") else msg_strip[4:]
        response_text = await run_in_threadpool(execute_cli_command, command)
    else:
        import sys
        
        scripts_dir = Path("/app/scripts")
        if not scripts_dir.exists():
            scripts_dir = Path(settings.PROJECT_ROOT) / "scripts"
        if str(scripts_dir) not in sys.path: pass
            
        from scripts.terminal_chat import build_system_prompt
        system_prompt = build_system_prompt("cloud", "Dashboard-Primary-LLM")
        
        session = chat_history_manager.get_session(session_id)
        
        history_context = ""
        for msg in session.get("messages", []):
            if msg["id"] == "initial" or msg["id"] == user_msg["id"]:
                continue
            history_context += f"\n- {msg['sender'].upper()}: {msg['content']}"
            
        full_user_message = f"CONVERSATIONAL HISTORY:{history_context}\n\nLATEST USER DIRECTIVE: {req.message}"
        
        try:
            max_iterations = 3
            current_iteration = 0
            
            while current_iteration < max_iterations:
                response_text = await run_in_threadpool(
                    call_llm_gateway,
                    system_prompt=system_prompt,
                    user_message=full_user_message,
                    temperature=0.3
                )
                
                if not response_text:
                    response_text = "I've logged your directive. However, my neural connection to the PRIMARY_LLM_URL failed."
                    break
                    
                commands = re.findall(r"```execute\n(.*?)\n```", response_text, re.DOTALL)
                if not commands:
                    break 
                    
                chat_history_manager.add_message_to_session(session_id, "kenbun", response_text)
                
                command = commands[0].strip()
                command_result = await run_in_threadpool(execute_cli_command, command)
                
                system_feedback = f"[SYSTEM OUT (Command: '{command}')]:\n{command_result}"
                chat_history_manager.add_message_to_session(session_id, "user", system_feedback)
                
                full_user_message = f"LATEST SYSTEM FEEDBACK: {system_feedback}\nPlease explain the result to the user or continue your process."
                current_iteration += 1
                
        except Exception as e:
            response_text = f"Neural Link Error: {str(e)}"
            
    ai_msg = chat_history_manager.add_message_to_session(session_id, "kenbun", response_text)
    updated_session = chat_history_manager.get_session(session_id)
    
    return {
        "user_message": user_msg,
        "ai_message": ai_msg,
        "session": updated_session
    }

@router.post("/api/v1/chat")
async def chat_with_kenbun(req: ChatRequest):
    """
    Passes user messages into the orchestrator/intelligence engine.
    Now functionally queries the active Primary LLM.
    """
    try:
        from core.tools.utils.llm_router import call_llm_gateway
        
        msg_strip = req.message.strip()
        
        if msg_strip.startswith("/run ") or msg_strip.startswith("run: "):
            command = msg_strip[5:] if msg_strip.startswith("/run ") else msg_strip[4:]
            response_text = await run_in_threadpool(execute_cli_command, command)
        else:
            import sys
            
            scripts_dir = Path("/app/scripts")
            if not scripts_dir.exists():
                scripts_dir = Path(settings.PROJECT_ROOT) / "scripts"
            if str(scripts_dir) not in sys.path: pass                
            from scripts.terminal_chat import build_system_prompt
            system_prompt = build_system_prompt("cloud", "Dashboard-Primary-LLM")
            
            response_text = await run_in_threadpool(
                call_llm_gateway,
                system_prompt=system_prompt,
                user_message=req.message,
                temperature=0.3
            )

            if not response_text:
                 response_text = f"I've logged your directive: '{req.message}'. However, my neural connection to the PRIMARY_LLM_URL failed. The Reflex workers are standing by."
                 
            commands = re.findall(r"```execute\n(.*?)\n```", response_text, re.DOTALL)
            if commands:
                command = commands[0].strip()
                command_result = await run_in_threadpool(execute_cli_command, command)
                system_feedback = f"[SYSTEM OUT (Command: '{command}')]:\n{command_result}"
                followup = f"LATEST SYSTEM FEEDBACK: {system_feedback}\nPlease explain the result."
                
                final_text = await run_in_threadpool(
                    call_llm_gateway,
                    system_prompt=system_prompt,
                    user_message=followup,
                    temperature=0.3
                )
                response_text = response_text + "\n\n" + final_text
            
        return {
            "response": response_text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logging.error(f"KENBUN_CHAT_ERROR: {e}")
        return {"response": f"Neural Link Error: {str(e)}", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.post("/dispatch/claude")
async def dispatch_to_claude(payload: dict):
    """
    Dispatches a deep coding task to the Claude Code CLI sub-agent.
    Activated when DecisionRouter assigns CLAUDE_CODE_PATH.
    Body: { "task": "...", "context_files": [...] }
    """
    task = payload.get("task", "")
    context_files = payload.get("context_files", [])

    if not task:
        return {"status": "error", "message": "No task provided"}

    if not claude_code_agent.is_available():
        return {
            "status": "unavailable",
            "message": "Claude Code CLI not installed. Run: npm install -g @anthropic-ai/claude-code"
        }

    result = claude_code_agent.dispatch(task, context_files=context_files or None, print_output=False)
    return {
        "status": "success" if result.success else "error",
        "output": result.output,
        "duration_seconds": result.duration_seconds,
        "error": result.error
    }

@router.get("/dispatch/p330/status")
async def p330_status():
    """Returns the health status of the P330 CPU Worker Node."""
    return p330_worker.ping()

@router.get("/kanban")
async def get_kanban_tasks():
    """
    Returns a structured list of tasks from both AG_TASKS.md and swarm_tasks.json.
    Prioritizes real mission telemetry for financial accuracy.
    """
    tasks = []
    
    if TASKS_FILE.exists():
        try:
            with open(TASKS_FILE, "r") as f:
                data = json.load(f)
                tasks.extend(data.get("tasks", []))
        except Exception as e:
            logging.error(f"MISSION_LEDGER_READ_ERROR: {e}")

    try:
        from core.tools.utils.workspace import workspace_manager
        projects = workspace_manager.get_projects()
        
        for project_path in projects:
            task_file = Path(project_path) / "AG_TASKS.md"
            if not task_file.exists():
                continue
                
            try:
                with open(task_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    
                for line in lines:
                    line = line.strip()
                    match = re.match(r"^-\s*\[([ x/])\]\s*(.*)$", line)
                    if not match:
                        continue
                    
                    status_char = match.group(1)
                    status = "todo" if status_char == " " else "doing" if status_char == "/" else "done" if status_char == "x" else "error"
                    content = match.group(2).strip()
                    
                    if any(t.get("objective") == content for t in tasks):
                        continue

                    model = "gemini-3-flash-preview"
                    if "[" in content and "]" in content:
                        match = re.search(r"\[(.*?)\]", content)
                        if match:
                            model = match.group(1)
                            content = content.replace(f"[{model}]", "").strip()

                    rates = token_governor.pricing.get(model, token_governor.pricing["gemini-3-flash-preview"])
                    est_tokens = 2000
                    est_cost = (est_tokens * rates["input"]) + (est_tokens * rates["output"])
                    
                    prob = 0.65
                    if any(k in content.lower() for k in ["security", "refactor", "optimize"]):
                        prob = 0.88
                    elif any(k in content.lower() for k in ["fix", "bug"]):
                        prob = 0.75
                        
                    tasks.append({
                        "id": f"{os.path.basename(project_path)}_{hash(content)}",
                        "project": os.path.basename(project_path),
                        "objective": content,
                        "status": status,
                        "model": model,
                        "est_cost": round(est_cost, 4),
                        "improvement_prob": prob,
                        "priority": "HIGH" if prob > 0.8 else "MEDIUM" if prob > 0.7 else "LOW"
                    })
            except Exception as e:
                logging.error(f"MD_TASK_READ_ERROR: {e}")
    except Exception as e:
         logging.error(f"Failed to fetch projects: {e}")
            
    return {"tasks": tasks}
