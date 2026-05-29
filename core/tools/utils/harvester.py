import os
import re
import json
from pathlib import Path

# --- CONFIGURATION ---
from tools.infrastructure.config import settings
PROJECT_ROOT = settings.PROJECT_ROOT
POST_MORTEM_PATH = PROJECT_ROOT / "POST_MORTEM.md"
TRAINING_DATA_DIR = PROJECT_ROOT / "training_data"
OUTPUT_FILE = TRAINING_DATA_DIR / "kenbun_dataset.jsonl"
INCOMING_LESSONS = TRAINING_DATA_DIR / "incoming_lessons.jsonl"

SYSTEM_PROMPT = (
    "You are Kenbun, a Senior CTO and Architect AI. Your goal is to build infinitely "
    "scalable, cost-efficient software. You follow the 'Augmented CTO' protocol: prioritizing "
    "local-first architecture, rigorous security audits (System 2), and local memory (System 3)."
)

def parse_post_mortem(content: str):
    """Parses the POST_MORTEM.md into structured training pairs."""
    failures = re.split(r'---|\n## 🔴 Failure', content)
    dataset = []
    for block in failures:
        if "**Symptoms:**" not in block or "**The Fix:**" not in block:
            continue
        title_match = re.search(r'^(.*?)\n', block.strip())
        symptoms_match = re.search(r'\*\*Symptoms:\*\*(.*?)\n\n\*\*Root Cause:\*\*', block, re.DOTALL)
        root_cause_match = re.search(r'\*\*Root Cause:\*\*(.*?)\n\n\*\*The Fix:\*\*', block, re.DOTALL)
        fix_match = re.search(r'\*\*The Fix:\*\*(.*?)$', block, re.DOTALL)
        if not (symptoms_match and root_cause_match and fix_match):
            continue
        title = title_match.group(1).strip() if title_match else "Unknown Issue"
        symptoms = symptoms_match.group(1).strip()
        root_cause = root_cause_match.group(1).strip()
        fix = fix_match.group(1).strip()
        user_prompt = f"I am seeing the following symptoms in my Kenbun system: {symptoms}\n\nCan you diagnose the root cause and provide a fix?"
        assistant_response = (
            f"Based on the symptoms, the root cause is: {root_cause}\n\n"
            f"**THE FIX:**\n{fix}\n\n"
            f"**ARCHITECTURAL LESSON:** To prevent this in the future, ensure that {title} is handled at the infrastructure level."
        )
        dataset.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": assistant_response}
            ]
        })
    return dataset

def harvest_gemini_plans():
    """Scans the .gemini directory for implementation plans and tasks."""
    gemini_dir = Path.home() / ".gemini" / "kenbun" / "brain"
    if not gemini_dir.exists():
        gemini_dir = Path.home() / ".gemini" / "kenbun" / "brain"
    dataset = []
    if not gemini_dir.exists():
        return []
    for conv_dir in gemini_dir.iterdir():
        if not conv_dir.is_dir():
            continue
        plan_file = conv_dir / "implementation_plan.md"
        if plan_file.exists():
            with open(plan_file, "r") as f:
                content = f.read()
            goal_match = re.search(r'# \[(.*?)\]', content)
            if goal_match:
                goal = goal_match.group(1)
                plan_summary = content[:500] + "..."
                user_prompt = f"What was the implementation plan for: {goal}?"
                assistant_response = f"For the goal '{goal}', we implemented the following strategy:\n\n{plan_summary}"
                dataset.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": assistant_response}
                    ]
                })
    return dataset

def ship_to_pc(lessons):
    """Ships distilled lessons to the PC brain for nightly baking."""
    PC_IP = settings.SWARM_PC_IP
    print(f"🛰️ Shipping {len(lessons)} lessons to the Neural Hub ({PC_IP})...")
    with open(INCOMING_LESSONS, "a") as f:
        for lesson in lessons:
            f.write(json.dumps(lesson) + "\n")
    print("✅ Lessons delivered to the Training Pool.")

def harvest():
    print(f"🚀 Starting Deep Kenbun Intelligence Harvest...")
    dataset = []
    
    # 1. Harvest Post-Mortems
    if POST_MORTEM_PATH.exists():
        with open(POST_MORTEM_PATH, "r") as f:
            dataset.extend(parse_post_mortem(f.read()))
            
    # 2. Harvest Gemini Plans
    dataset.extend(harvest_gemini_plans())
    
    # 3. Scrub Supabase
    scrubbed_dataset = []
    for entry in dataset:
        entry_str = json.dumps(entry)
        if "Supabase" in entry_str:
            scrubbed_str = entry_str.replace("Supabase", "Local-First Architecture")
            scrubbed_dataset.append(json.loads(scrubbed_str))
        else:
            scrubbed_dataset.append(entry)

    # 4. Ship to PC
    if scrubbed_dataset:
        ship_to_pc(scrubbed_dataset)
    else:
        print("💤 No new high-quality data found today. Resting.")

if __name__ == "__main__":
    harvest()
