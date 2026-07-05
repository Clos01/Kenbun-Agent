import os
import json
import shutil
import asyncio
import logging
from typing import Optional, Dict, Any, List

from tools.registry import sovereign_tool

logger = logging.getLogger("imessage_tools")

def get_imsg_path() -> Optional[str]:
    """Helper to check if imsg is installed."""
    return shutil.which("imsg")

@sovereign_tool(name="list_imessage_chats", category="Sensory")
async def list_imessage_chats(limit: int = 10) -> Dict[str, Any]:
    """
    List recent iMessage/SMS chats from Messages.app.
    
    Args:
        limit: Max number of recent chats to return.
    """
    imsg_path = get_imsg_path()
    if not imsg_path:
        return {
            "success": False,
            "error": "imsg CLI is not installed or not found in PATH. Please run 'brew install steipete/tap/imsg' on macOS."
        }
        
    cmd = [imsg_path, "chats", "--limit", str(limit), "--json"]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return {
                "success": False,
                "error": f"imsg command failed with exit code {proc.returncode}: {stderr.decode(errors='ignore')}"
            }
            
        data = json.loads(stdout.decode(errors='ignore'))
        return {
            "success": True,
            "chats": data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list iMessage chats: {str(e)}"
        }

@sovereign_tool(name="get_imessage_history", category="Sensory")
async def get_imessage_history(
    chat_id: int,
    limit: int = 20,
    attachments: bool = False
) -> Dict[str, Any]:
    """
    Retrieve message history for a specific chat ID.
    
    Args:
        chat_id: The ID of the chat database entry.
        limit: Max number of messages to retrieve.
        attachments: Whether to include details about file attachments.
    """
    imsg_path = get_imsg_path()
    if not imsg_path:
        return {
            "success": False,
            "error": "imsg CLI is not installed or not found in PATH."
        }
        
    cmd = [imsg_path, "history", "--chat-id", str(chat_id), "--limit", str(limit), "--json"]
    if attachments:
        cmd.append("--attachments")
        
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return {
                "success": False,
                "error": f"imsg command failed with exit code {proc.returncode}: {stderr.decode(errors='ignore')}"
            }
            
        data = json.loads(stdout.decode(errors='ignore'))
        return {
            "success": True,
            "messages": data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get message history: {str(e)}"
        }

@sovereign_tool(name="send_imessage", category="Sensory")
async def send_imessage(
    to: str,
    text: str,
    file: Optional[str] = None,
    service: str = "auto"
) -> Dict[str, Any]:
    """
    Send an iMessage or SMS to a contact number or Apple ID email.
    
    Args:
        to: Recipient phone number (e.g. +1555123456) or Apple ID email.
        text: The message body content to send.
        file: Optional absolute path to a file attachment (image, pdf, etc.).
        service: Protocol service to force ('imessage', 'sms', or 'auto').
    """
    imsg_path = get_imsg_path()
    if not imsg_path:
        return {
            "success": False,
            "error": "imsg CLI is not installed or not found in PATH."
        }
        
    if not to.strip():
        return {"success": False, "error": "Recipient ('to') cannot be empty."}
        
    if not text.strip():
        return {"success": False, "error": "Message text ('text') cannot be empty."}
        
    if service not in ["imessage", "sms", "auto"]:
        return {"success": False, "error": f"Invalid service '{service}'. Must be 'imessage', 'sms', or 'auto'."}

    cmd = [imsg_path, "send", "--to", to, "--text", text]
    
    if file:
        file_path = os.path.abspath(file)
        if not os.path.exists(file_path):
            return {"success": False, "error": f"Attachment file does not exist: {file_path}"}
        cmd.extend(["--file", file_path])
        
    if service != "auto":
        cmd.extend(["--service", service])
        
    try:
        logger.info(f"Sending iMessage/SMS to {to} using service={service}...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return {
                "success": False,
                "error": f"imsg command failed with exit code {proc.returncode}: {stderr.decode(errors='ignore')}"
            }
            
        return {
            "success": True,
            "message": f"Successfully sent message to {to}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send iMessage: {str(e)}"
        }
