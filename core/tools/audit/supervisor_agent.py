import os
import json
import requests
import asyncio
from pathlib import Path
from tools.utils.llm_utils import extract_json

# --- 1. ENSEMBLE INTEGRATION ---
try:
    from tools.audit.ensemble_audit import ensemble
except ImportError:
    ensemble = None

try:
    from tools.audit.adversarial_court import adversarial_court
except ImportError:
    adversarial_court = None

# Try to import Gemini reviewer for high-fidelity audits
try:
    from tools.audit.gemini_reviewer import call_gemini_pro, gemini_code_review
except ImportError:
    # Use lazy imports or placeholders if the reviewer isn't available
    def call_gemini_pro(prompt: str): return None
    def gemini_code_review(*args, **kwargs): return None

from tools.infrastructure.config import settings
from tools.design.guardrail import DesignGuardrail
from tools.infrastructure.topology_manager import log_swarm_event

def _call_local_senior(system_prompt: str, user_message: str):
    """Call the hardware-agnostic LLM gateway."""
    import time
    start_time = time.time()
    try:
        from tools.utils.llm_router import call_llm_gateway
        content = call_llm_gateway(system_prompt, user_message)
        duration = time.time() - start_time
        
        try:
            from tools.strategy.decision_logic import router
            router.record_model_feedback(
                model="local",
                task=user_message,
                success=True,
                latency=duration,
                cost=0.0
            )
        except Exception as routing_err:
            print(f"⚠️ Failed to record local model feedback: {routing_err}")
            
        return content, None
    except Exception as e:
        duration = time.time() - start_time
        try:
            from tools.strategy.decision_logic import router
            router.record_model_feedback(
                model="local",
                task=user_message,
                success=False,
                latency=duration,
                cost=0.0
            )
        except Exception as routing_err:
            print(f"⚠️ Failed to record local model feedback: {routing_err}")
            
        return None, f"❌ Local Senior Fallback failed: {e}"

class TriageManager:
    """Handles automatic triage of audit proposals."""
    UI_KEYWORDS = ["css", "style", "layout", "color", "aesthetic", "glassmorphism", "tailwind"]
    CRITICAL_KEYWORDS = ["auth", "database", "password", "security", "token", "env", "sql", "route"]

    @classmethod
    def triage(cls, user_proposal: str, code_snippet: str) -> str:
        prop_lower = user_proposal.lower()
        snippet_lower = code_snippet.lower()
        
        is_ui = any(k in prop_lower or k in snippet_lower for k in cls.UI_KEYWORDS)
        is_critical = any(k in prop_lower or k in snippet_lower for k in cls.CRITICAL_KEYWORDS)
        
        if is_ui and not is_critical:
            return "UI_STYLE"
        return "CRITICAL"

async def _tier_1_local(user_proposal: str, code_snippet: str):
    if not ensemble:
        return None
    try:
        res = await ensemble.run_audit(user_proposal, code_snippet)
        verdict = res.get("verdict")
        if verdict in ["APPROVED", "REJECTED"]:
            print(f"✅ [ENSEMBLE] Consensus reached: {verdict} (Score: {res['score']:.2f})")
            return {
                "status": verdict,
                "critique": res.get("reason"),
                "confidence": abs(res.get("score", 0)),
                "votes": res.get("votes"),
                "tier": "Tier 1: Local Ensemble"
            }
        return verdict # Could be HUNG_JURY
    except Exception as e:
        print(f"⚠️ [ENSEMBLE] Audit error: {e}")
        return None

async def _synthesize_review_reason_locally(raw_critique: str, proposal: str) -> str:
    """Uses the local Gemma 26B model via LM Studio to summarize and write a clear manual review explanation, saving cloud cost."""
    print("📝 [SYSTEM 2] Calling local Gemma model to synthesize manual review reason (saving cloud cost)...")
    system_prompt = (
        "You are the Local Senior Architect. A code audit/review requires manual human intervention (REVIEW_NEEDED).\n"
        "Draft a clear, concise, and highly professional explanation of WHY this manual review is needed.\n"
        "Be extremely specific about security risks, architectural concerns, or visual mismatches.\n"
        "Cite the specific problems identified in the raw critique.\n"
        "Explicitly start your response with: '[LOCAL MODEL SYNTHESIS - SAVING CLOUD COST]'"
    )
    user_message = f"RAW CRITIQUE:\n{raw_critique}\n\nUSER PROPOSAL:\n{proposal}"
    
    local_explanation, err = _call_local_senior(system_prompt, user_message)
    if not err and local_explanation:
        return local_explanation
    
    return f"[FALLBACK] Manual review is required. Could not run local synthesis: {err}. Raw critique: {raw_critique}"

async def _fetch_digested_rules() -> str:
    """Retrieves the synthesized architectural rules from the Local Digestion Loop."""
    try:
        from tools.memory.chroma_db_connect import get_project_collection
        collection = get_project_collection("digested_rules")
        if not collection:
            return ""
        # Get the 3 most recent rules
        results = collection.get(limit=3, include=['documents'])
        if results and results.get('documents'):
            return "\n\n".join(results['documents'])
    except Exception as e:
        print(f"⚠️ [SYSTEM 2] Failed to fetch digested rules: {e}")
    return ""

async def _tier_2_cloud(user_proposal: str, code_snippet: str, memory_context: str, tech_key: str, local_verdict: str):
    print("🔮 [SYSTEM 2] Escalating to Supreme Evaluator (DeepSeek Tier 2)...")
    
    digested_rules = await _fetch_digested_rules()
    rules_context = f"\n\nDIGESTED ARCHITECTURAL RULES:\n{digested_rules}" if digested_rules else ""
    context = f"PROPOSAL: {user_proposal}\nMEMORY: {memory_context}{rules_context}"
    
    system_prompt = (
        "You are the Supreme Evaluator (Tier 2). Review the following code proposal strictly against "
        "the provided DIGESTED ARCHITECTURAL RULES and Context. "
        "Return a valid JSON object matching this schema:\n"
        '{"status": "APPROVED" | "REJECTED" | "REVIEW_NEEDED", "critique": "Detailed reasoning here"}'
    )
    user_message = f"CONTEXT:\n{context}\n\nCODE:\n{code_snippet}"
    
    try:
        from tools.utils.llm_router import call_llm_gateway
        # The llm_router will naturally route to DeepSeek if configured, or the default fallback
        result = call_llm_gateway(system_prompt, user_message)
        
        if result:
            res_obj = extract_json(result)
            if res_obj:
                # Consensus logic
                if local_verdict and "status" in res_obj:
                    print(f"🤝 [SYSTEM 2] Consensus Check: Supreme({res_obj['status']}) vs Local({local_verdict})")
                    if res_obj["status"] == "REJECTED" and local_verdict == "APPROVED":
                         print("⚖️ [SYSTEM 2] Conflict Detected. Supreme REJECTED what Local APPROVED. Prioritizing Security (REJECTED).")
                         res_obj["status"] = "REJECTED"
                         res_obj["critique"] += "\n[CONSENSUS OVERRIDE]: Security priority rejection."
                
                if res_obj.get("status") == "REVIEW_NEEDED":
                    explanation = await _synthesize_review_reason_locally(res_obj.get("critique", ""), user_proposal)
                    res_obj["critique"] = explanation
                
                res_obj["tier"] = "Tier 2: Supreme Evaluator (DeepSeek)"
                return res_obj
                
    except Exception as e:
        print(f"⚠️ [SYSTEM 2] Supreme Evaluator failed: {e}")
        
    return None

async def _tier_3_fallback(user_proposal: str, code_snippet: str, memory_context: str):
    print(f"🔄 [SYSTEM 2] Falling back to Local Senior Architect ({settings.models.lm_studio_model})...")
    system_prompt = (
        "You are THE SUPERVISOR (System 2), the lead architect and security officer. "
        "Review the following proposal and code for deep systemic risks."
    )
    context = f"PROPOSAL: {user_proposal}\nMEMORY: {memory_context}"
    prompt = f"CONTEXT: {context}\n\nCODE:\n{code_snippet}"
    
    for attempt in range(2):
        raw_result, err = _call_local_senior(system_prompt, prompt)
        if err:
            print("☁️ [SYSTEM 2] Local Senior Architect unavailable. Falling back to Gemini Cloud AI...")
            try:
                raw_result = gemini_code_review(
                    code_snippet=code_snippet,
                    review_context=f"PROPOSAL: {user_proposal}\nMEMORY: {memory_context}",
                    cross_check=False
                )
                if raw_result:
                    res_obj = extract_json(raw_result)
                    if res_obj:
                        res_obj["tier"] = "Tier 3 Fallback: Gemini Cloud AI Reviewer"
                        return res_obj
            except Exception as gem_err:
                print(f"⚠️ [SYSTEM 2] Gemini Fallback also failed: {gem_err}")
            return {"status": "ERROR", "critique": f"Audit failed: {err}"}

        res_obj = extract_json(raw_result)
        if res_obj:
            res_obj["tier"] = "Tier 3: Local Senior Fallback (LM Studio/Ollama)"
            return res_obj
        
        if attempt == 0:
            prompt += f"\n\nIMPORTANT: Return ONLY a valid JSON object."
        else:
            return {"status": "REJECTED", "critique": f"Parse failure: {raw_result[:200]}"}

async def run_supervisor_audit(user_proposal: str, code_snippet: str = "", memory_context: str = "", tech_key: str = ""):
    """
    Executes a high-fidelity System 2 Executive Audit.
    Automatically triages between CRITICAL and UI_STYLE.
    """
    category = TriageManager.triage(user_proposal, code_snippet)
    print(f"🏛️ [SYSTEM 2] Initiating Executive Supervisor Audit ({category})...")
    
    if category == "UI_STYLE":
        print("🎨 [SYSTEM 2] UI/STYLE Detected. Running Fast-Track Style Audit...")
        # NEW: Integrate Heritage Design Guardrail
        style_res = DesignGuardrail.validate(code_snippet)
        if style_res["status"] == "REJECTED":
            print(f"🚩 [SYSTEM 2] Heritage Design Violation: {style_res['reason']}")
            res_style = {
                "status": "REJECTED",
                "critique": f"Design Compliance Failure: {style_res['reason']}",
                "tier": "System 2c: Design Guardrail"
            }
            log_swarm_event("DECISION", {
                "tool": "supervisor_agent", 
                "confidence": 1.0, 
                "result": "REJECTED", 
                "logic": "Design Guardrail",
                "output": res_style["critique"]
            })
            return res_style
        print("✅ [SYSTEM 2] Heritage Design Compliance Verified.")

    # Tier 1a: Adversarial LLM Court (Judge & Defendant Trial)
    if adversarial_court:
        try:
            res_court = await adversarial_court.run_trial(user_proposal, code_snippet)
            if res_court and res_court.get("verdict") in ["APPROVED", "REJECTED"]:
                print(f"✅ [COURT] Verdict rendered: {res_court['verdict']} (Confidence: {res_court['confidence']:.2f})")
                res_court_formatted = {
                    "status": res_court["verdict"],
                    "critique": f"[ADVERSARIAL COURT] Verdict: {res_court['verdict']}\n"
                                f"Critique: {res_court['critique']}",
                    "confidence": res_court["confidence"],
                    "tier": "System 2a: Adversarial LLM Court"
                }
                log_swarm_event("DECISION", {
                    "tool": "supervisor_agent", 
                    "confidence": res_court["confidence"], 
                    "result": res_court["verdict"], 
                    "logic": "System 2a: Adversarial LLM Court",
                    "output": res_court_formatted["critique"]
                })
                return res_court_formatted
        except Exception as court_err:
            print(f"⚠️ [COURT] Adversarial court trial failed, falling back to local ensemble: {court_err}")

    # Tier 1: Local Ensemble
    res = await _tier_1_local(user_proposal, code_snippet)
    if isinstance(res, dict):
        log_swarm_event("DECISION", {
            "tool": "supervisor_agent", 
            "confidence": res.get("confidence", 0.5), 
            "result": res.get("status", "UNKNOWN"), 
            "logic": "Tier 1: Local Ensemble",
            "output": res.get("critique", "No critique details provided.")
        })
        return res
    
    local_verdict = res # HUNG_JURY or None
    if local_verdict == "HUNG_JURY":
        print("⚖️ [ENSEMBLE] Hung Jury detected. Escalating to Cloud for tie-breaking...")

    # Tier 2: Cloud Escalation
    res = await _tier_2_cloud(user_proposal, code_snippet, memory_context, tech_key, local_verdict)
    if res:
        log_swarm_event("DECISION", {
            "tool": "supervisor_agent", 
            "confidence": 0.9, 
            "result": res.get("status", "UNKNOWN"), 
            "logic": "Tier 2: Cloud Escalation",
            "output": res.get("critique", "No critique details provided.")
        })
        return res

    # Tier 3: Local Senior Fallback
    res = await _tier_3_fallback(user_proposal, code_snippet, memory_context)
    log_swarm_event("DECISION", {
        "tool": "supervisor_agent", 
        "confidence": 0.5, 
        "result": res.get("status", "UNKNOWN") if isinstance(res, dict) else "UNKNOWN", 
        "logic": "Tier 3: Fallback",
        "output": res.get("critique", "No critique details provided.") if isinstance(res, dict) else str(res)
    })
    return res
