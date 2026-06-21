"""Chat and conversational session routes.

Provides endpoints for managing chat sessions (CRUD) and sending
messages through the Kenbun LLM gateway—both stateless single-shot
chat and stateful session-based conversations with autonomous
command-execution loops.
"""

import re
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from tools.infrastructure.server_deps import verify_authorization, execute_cli_command

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to Hermes")


class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field("New Transmissions", description="Initial title of the session")


class ChatSessionMessageRequest(BaseModel):
    message: str = Field(..., description="The user message to send")


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

@router.get("/api/v1/chat/sessions")
async def get_chat_sessions():
    from tools.utils import chat_history_manager
    return chat_history_manager.list_sessions()


@router.post("/api/v1/chat/sessions", dependencies=[Depends(verify_authorization)])
async def create_chat_session(req: Optional[CreateSessionRequest] = None):
    from tools.utils import chat_history_manager
    title = req.title if req and req.title else "New Transmissions"
    return chat_history_manager.create_session(title=title)


@router.get("/api/v1/chat/sessions/{session_id}")
async def get_chat_session(session_id: str):
    from tools.utils import chat_history_manager
    session = chat_history_manager.get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": f"Session {session_id} not found"})
    return session


@router.delete("/api/v1/chat/sessions/{session_id}", dependencies=[Depends(verify_authorization)])
async def delete_chat_session(session_id: str):
    from tools.utils import chat_history_manager
    success = chat_history_manager.delete_session(session_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": f"Session {session_id} not found"})
    return {"status": "success", "message": f"Session {session_id} deleted"}


# ---------------------------------------------------------------------------
# Session-based messaging (stateful, with LLM gateway + command loop)
# ---------------------------------------------------------------------------

@router.post("/api/v1/chat/sessions/{session_id}/message", dependencies=[Depends(verify_authorization)])
async def post_message_to_session(session_id: str, req: ChatSessionMessageRequest):
    """Sends a message within an existing chat session and queries the AI using history context."""
    from tools.utils import chat_history_manager
    from tools.utils.llm_router import call_llm_gateway

    # 1. Verify session exists
    session = chat_history_manager.get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": f"Session {session_id} not found"})

    # 2. Append user message to history
    user_msg = chat_history_manager.add_message_to_session(session_id, "user", req.message)

    # 3. Direct /run Command Hook (Sovereign Command Execution on Hardware)
    msg_strip = req.message.strip()
    if msg_strip.startswith("/run ") or msg_strip.startswith("run: "):
        command = msg_strip[5:] if msg_strip.startswith("/run ") else msg_strip[4:]
        response_text = await run_in_threadpool(execute_cli_command, command)
    else:
        # 4. Compile full conversational context from history (using Terminal Chat's exact System 1-6 rules)
        from pathlib import Path
        from tools.infrastructure.config import settings

        scripts_dir = Path("/app/scripts")
        if not scripts_dir.exists():
            scripts_dir = Path(settings.PROJECT_ROOT) / "scripts"

        import sys
        if str(scripts_dir.parent) not in sys.path:
            sys.path.insert(0, str(scripts_dir.parent))
        from scripts.terminal_chat import build_system_prompt
        system_prompt = build_system_prompt("cloud", "Dashboard-Primary-LLM")

        # Re-fetch session to include the newly appended message
        session = chat_history_manager.get_session(session_id)

        # Formulate conversational prompt by pairing up past messages
        history_context = ""
        for msg in session.get("messages", []):
            if msg["id"] == "initial" or msg["id"] == user_msg["id"]:
                continue
            history_context += f"\n- {msg['sender'].upper()}: {msg['content']}"

        full_user_message = f"CONVERSATIONAL HISTORY:{history_context}\n\nLATEST USER DIRECTIVE: {req.message}"

        try:
            # 5. Call LLM (with auto-execution loop for System 1-6 tools)
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
                    break  # Normal conversational response

                # We have a command! Save the AI's thought process
                chat_history_manager.add_message_to_session(session_id, "kenbun", response_text)

                # Execute the first command found autonomously
                command = commands[0].strip()
                command_result = await run_in_threadpool(execute_cli_command, command)

                # Feed the result back into history as a 'user' message representing System Feedback
                system_feedback = f"[SYSTEM OUT (Command: '{command}')]:\n{command_result}"
                chat_history_manager.add_message_to_session(session_id, "user", system_feedback)

                # Update loop variables to ask the LLM to process the result
                full_user_message = f"LATEST SYSTEM FEEDBACK: {system_feedback}\nPlease explain the result to the user or continue your process."
                current_iteration += 1

        except Exception as e:
            response_text = f"Neural Link Error: {str(e)}"

    # 6. Append final AI response to history
    ai_msg = chat_history_manager.add_message_to_session(session_id, "kenbun", response_text)

    # Reload session to return latest state
    updated_session = chat_history_manager.get_session(session_id)

    return {
        "user_message": user_msg,
        "ai_message": ai_msg,
        "session": updated_session
    }


# ---------------------------------------------------------------------------
# Stateless chat (single-shot, with one-pass command execution)
# ---------------------------------------------------------------------------

@router.post("/api/v1/chat", dependencies=[Depends(verify_authorization)])
async def chat_with_kenbun(req: ChatRequest):
    """
    Passes user messages into the orchestrator/intelligence engine.
    Now functionally queries the active Primary LLM.
    """
    try:
        from tools.utils.llm_router import call_llm_gateway

        msg_strip = req.message.strip()

        # 1. Direct /run Command Hook (Sovereign Command Execution on Hardware)
        if msg_strip.startswith("/run ") or msg_strip.startswith("run: "):
            command = msg_strip[5:] if msg_strip.startswith("/run ") else msg_strip[4:]
            response_text = await run_in_threadpool(execute_cli_command, command)
        else:
            # 2. Functional Chat Pass-Through to the LLM
            from pathlib import Path
            from tools.infrastructure.config import settings

            scripts_dir = Path("/app/scripts")
            if not scripts_dir.exists():
                scripts_dir = Path(settings.PROJECT_ROOT) / "scripts"

            import sys
            if str(scripts_dir.parent) not in sys.path:
                sys.path.insert(0, str(scripts_dir.parent))
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

            # 3. Handle autonomous commands for stateless chat
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
