from tools.infrastructure.design_bridge import spawn_design_agent, detect_available_agents
from tools.utils.orchestrator_helpers import build_context

def run_design_agent_with_fallback(tools, **kwargs):
    """
    Attempts to spawn a local design agent via the bridge.
    If the bridge fails (AgentNotFoundError, Timeout, etc.), falls back to review_code_with_gemini.
    """
    agent_id = kwargs.get("agent_id", "gemini")
    available = detect_available_agents()
    
    # Check if preferred agent is available
    if any(a["id"] == agent_id for a in available):
        result = spawn_design_agent(
            agent_id=agent_id,
            task=kwargs.get("task", ""),
            design_system=kwargs.get("design_system", "default"),
            skill=kwargs.get("skill", "web-prototype")
        )
        
        # If the bridge returned an error string, we treat it as a failure for fallback
        if result.startswith("Bridge Error:") or result.startswith("Error:"):
            print(f"⚠️ Design Bridge failed: {result}. Falling back to Cloud AI...")
        else:
            return result

    # Fallback to Cloud AI (review_code_with_gemini)
    return tools["review_code_with_gemini"](**kwargs)


def build_design_ui_pipeline(tools):
    """
    Pipeline: discovery → strategy → research → implement → audit
    Use case: "Design a new mobile onboarding flow"
    """
    return [
        {
            "id": "generate_discovery_form",
            "label": "📋 System 5: Locking the Design Brief",
            "tool": tools["generate_discovery_form"],
            "input": lambda s: {"task_description": s["task"]},
            "output_key": "discovery_brief",
        },
        {
            "id": "research_design",
            "label": "🔍 Researching Design Systems",
            "tool": tools["research_with_gemini"],
            "input": lambda s: {
                "query": f"Analyze best practices for {s['task']} based on DESIGN.md",
                "tech_key": s.get("tech_key", "tailwind")
            },
            "output_key": "design_research",
        },
        {
            "id": "generate_artifact",
            "label": "🎨 Emitting Design Artifact",
            "tool": lambda **kwargs: run_design_agent_with_fallback(tools, **kwargs),
            "input": lambda s: {
                "agent_id": s.get("preferred_agent", "gemini"),
                "task": s["task"],
                "design_system": s.get("design_system", "default"),
                "skill": s.get("skill", "web-prototype"),
                # Fallback inputs for review_code_with_gemini
                "code_snippet": s.get("code_snippet", "No existing code"),
                "review_context": f"GOAL: {s['task']}\nRESEARCH: {s.get('design_research', '')}\nBRIEF: {s.get('discovery_brief', '')}\n\nStrictly follow DESIGN.md rules. Output a single <artifact> block.",
                "tech_key": "nextjs",
                "cross_check": True,
            },
            "output_key": "artifact_result",
        },
        {
            "id": "design_audit",
            "label": "⚖️ System 2: 5-Dimensional Design Audit",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": f"Audit this design against: Philosophy, Hierarchy, Detail, Function, Innovation.",
                "code_snippet": s.get("artifact_result", "")
            },
            "output_key": "audit_score",
        },
    ]
