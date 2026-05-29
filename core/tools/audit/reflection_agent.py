import os
import json
from pathlib import Path
from tools.audit.gemini_reviewer import _call_gemini
from tools.memory.knowledge_manager import learn_concept
import time

from tools.infrastructure.config import settings
TELEMETRY_PATH = settings.BRAIN_HEALTH_DIR / "live_telemetry.json"

def log_reflection(message: str, data: dict = None):
    try:
        log_entry = {
            "timestamp": time.time(),
            "message": message,
            "type": "reflection",
            "data": data
        }
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except:
        pass

def reflect_and_distill(task: str, tool_logs: str) -> str:
    """
    Analyzes the task and tool execution logs to extract architectural patterns, 
    lessons learned, or reusable concepts for the Hivemind.
    """
    print(f"🧠 System 5: Reflecting on task: {task}...")

    system_prompt = (
        "You are a Senior Systems Architect (System 5: The Reflection Layer). "
        "Your job is to analyze an AI agent's execution log and extract high-value 'Concepts' "
        "that should be saved to the permanent Hivemind knowledge base.\n\n"
        "Rules:\n"
        "1. Identify generic architectural rules (e.g., 'Always use UUIDs in PostgreSQL').\n"
        "2. Identify 'Lessons Learned' from failures or backtracking.\n"
        "3. Ignore specific details (like specific filenames or API keys).\n"
        "4. Format your output as a JSON object with two keys:\n"
        "   - 'concepts': List of [{\"title\": \"...\", \"content\": \"...\", \"tags\": \"...\"}].\n"
        "   - 'tuning': List of tool performance updates: [{\"tool_id\": \"...\", \"success\": bool, \"category\": \"security\"|\"frontend\"|\"logic\"|\"research\"}]\n\n"
        "Be concise but deep. One high-quality concept is better than five shallow ones."
    )

    user_message = f"""
    TASK: {task}
    TOOL EXECUTION LOGS:
    {tool_logs}
    """

    try:
        # Use Gemini to distill concepts
        distilled_text = _call_gemini(system_prompt, user_message, temperature=0.3)
        
        # Clean potential markdown from response
        clean_text = distilled_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        
        concepts = data.get("concepts", [])
        tuning = data.get("tuning", [])
        
        results = []
        for concept in concepts:
            title = concept.get("title")
            content = concept.get("content")
            tags = concept.get("tags", "reflection")
            
            # Save to Hivemind
            save_result = learn_concept(title, content, tags)
            results.append(f"- Concept: {title}: {save_result}")
            
            # Broadcast to Dashboard
            log_reflection(f"Distilled Concept: {title}", {"content": content, "tags": tags})
            
        # Return tuning data for the Orchestrator to apply
        tuning_report = []
        for t in tuning:
            tuning_report.append(f"- Tune: {t['tool_id']} ({t['category']}) -> {'Success' if t['success'] else 'Failure'}")

        if not results and not tuning_report:
            log_reflection("Reflection complete: No high-value concepts or tuning identified.")
            return "Reflection complete: No high-value concepts identified."
            
        report = "🧠 Distilled Concepts & Tuning Suggestions:\n" + "\n".join(results + tuning_report)
        return {
            "report": report,
            "tuning_payload": tuning
        }

    except Exception as e:
        return f"❌ Reflection failed: {e}\nRaw Output: {distilled_text[:500] if 'distilled_text' in locals() else 'N/A'}"
