import os
import sys
import json
import time
from pathlib import Path

# Setup paths to import core tools
from tools.infrastructure.config import settings
project_root = settings.PROJECT_ROOT
from tools.infrastructure.server import get_intelligence_stats, get_brain_health, query_system_3

from tools.memory.knowledge_manager import list_concepts
from tools.audit.supervisor_agent import run_supervisor_audit

async def generate_self_awareness_report():
    """
    Analyzes the AI's own performance and memory state.
    """
    print("🧠 Starting Self-Awareness Analysis...")
    
    # 1. Gather Telemetry
    health = get_brain_health()
    stats = get_intelligence_stats()
    
    # 2. Analyze Knowledge Base Size
    concepts_raw = list_concepts("architectural rules", n_results=100)
    try:
        concepts = json.loads(concepts_raw)
        concept_count = len(concepts)
    except Exception:
        concept_count = 0
        
    # 3. Identify Weakest Tool
    # (Simple string parsing for this demo, usually we'd query the DB directly)
    weak_tool = "None"
    lowest_prob = 1.0
    for line in stats.split("\n"):
        if "**" in line:
            try:
                name = line.split("**")[1]
                prob_str = line.split(":")[1].split("%")[0].strip()
                prob = float(prob_str) / 100
                if prob < lowest_prob:
                    lowest_prob = prob
                    weak_tool = name
            except Exception:
                continue
    
    # 4. Security Check
    api_key_secret = settings.GEMINI_API_KEY
    is_encrypted = api_key_secret.get_secret_value().startswith("enc:") if api_key_secret else False
    
    # 5. Supervisor Audit (System 2)
    print("🧠 Consulting Supervisor for system audit...")
    audit_proposal = f"Audit the current system state. Knowledge Base: {concept_count} concepts. Weakest tool: {weak_tool}."
    memory_context = query_system_3("architectural standards")
    supervisor_critique = await run_supervisor_audit(audit_proposal, memory_context=memory_context)

    # 5. Generate Report
    report = [
        "# 🤖 Kenbun Self-Awareness Report",
        f"**Date:** {time.ctime()}",
        "",
        "## 📈 Current Health Status",
        health,
        "",
        "## 🧠 Knowledge Density",
        f"- **Hivemind Concepts:** {concept_count}",
        f"- **Knowledge Gap:** {'CRITICAL' if concept_count < 10 else 'HEALTHY'}",
        "",
        "## ⚖️ Supervisor (System 2) Audit",
        f"**Status:** {supervisor_critique.get('status', 'Unknown').upper()}",
        f"**Risk Level:** {supervisor_critique.get('risk_level', 'Unknown').upper()}",
        f"**Critique:** {supervisor_critique.get('critique', 'N/A')}",
        f"**Instruction:** {supervisor_critique.get('improvement_instruction', 'N/A')}",
        "",
        "## 🔒 Security & Infrastructure Audit",
        f"- **API Key Encryption:** {'SECURE ✅' if is_encrypted else 'VULNERABLE 🔴'}",
        f"- **Master Key Found:** {'YES ✅' if (project_root / '.kenbun_master.key').exists() else 'NO 🔴'}",
        f"- **Infrastructure Mode:** LOCAL-FIRST PC (No-Supabase) ✅",
        "",
        "## 🎯 Primary Optimization Target",
        f"Tool: **{weak_tool}** ({lowest_prob:.2%})",
        f"Recommendation: Check local PC connectivity and tool weights",
        "",
        "## 🚀 Suggested Action Plan",
        "1. **Distillation**: Run more 'research_implement' tasks to fill the Hivemind.",
        "2. **Pruning**: Delete any concepts tagged as 'experimental' that are older than 7 days.",
        "3. **Local Testing**: Run the sandbox runner on known failures to verify Docker stability."
    ]
    
    return "\n".join(report)

if __name__ == "__main__":
    import asyncio
    report = asyncio.run(generate_self_awareness_report())
    output_path = Path(__file__).parent / "SOTU_REPORT.md"
    with open(output_path, "w") as f:
        f.write(report)
    print(f"✅ State of the Union report generated at {output_path}")
    print("\n" + report)
