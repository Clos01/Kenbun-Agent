"""
System 5 Discovery Agent — The "Discovery Form" Generator.
Ensures every design task starts with a strategic brief lock-in.
"""
import json
import os
from pathlib import Path

# Mock or real LLM call for discovery
def generate_discovery_form(task_description: str):
    """
    Analyzes the task and produces a JSON schema for a discovery form.
    In a real implementation, this would call Gemini 2.0 Flash to brainstorm questions.
    """
    print(f"🧠 [DISCOVERY] Generating strategic brief for: {task_description}")
    
    # Static fallback for now, but designed to be dynamic
    form = {
        "id": "discovery_form_1",
        "title": "Design Strategy Brief",
        "questions": [
            {
                "id": "surface",
                "label": "Surface / Platform",
                "type": "select",
                "options": ["Desktop Web", "Mobile App (iOS/Android)", "Responsive Landing", "Pitch Deck", "Email Marketing"],
                "default": "Desktop Web"
            },
            {
                "id": "audience",
                "label": "Target Audience",
                "type": "text",
                "placeholder": "e.g. Crypto Investors, Senior Architects, Gen Z Foodies",
                "default": "Professional/General"
            },
            {
                "id": "tone",
                "label": "Visual Direction (The 5 Schools)",
                "type": "radio",
                "options": [
                    "Filmic Monolith (Kenbun Default)",
                    "Modern Minimal (Linear/Stripe)",
                    "Editorial (Monocle/FT)",
                    "Tech Utility (Monospace/Bloomberg)",
                    "Brutalist (Experimental/Bold)"
                ],
                "default": "Filmic Monolith (Kenbun Default)"
            },
            {
                "id": "constraints",
                "label": "Primary Constraints",
                "type": "checkbox",
                "options": ["No External Assets", "High Motion (Framer)", "Glassmorphism Focus", "Print-Ready Layout"],
                "default": ["High Motion (Framer)", "Glassmorphism Focus"]
            }
        ],
        "metadata": {
            "task": task_description,
            "status": "pending_user_input"
        }
    }
    
    # Save the form to the telemetry stream so the UI can pick it up
    from tools.infrastructure.config import settings
    TELEMETRY_PATH = settings.BRAIN_HEALTH_DIR / "live_telemetry.json"
    try:
        data = {
            "timestamp": 123456789, # Placeholder or use time.time()
            "type": "discovery_form",
            "form": form
        }
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(data) + "\n")
    except Exception as e:
        print(f"⚠️ Failed to broadcast discovery form: {e}")

    return form

if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "Build a landing page"
    print(json.dumps(generate_discovery_form(task), indent=2))
