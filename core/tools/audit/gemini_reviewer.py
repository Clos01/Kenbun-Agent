"""
Gemini Code Reviewer — Cloud-based AI review with cross-validation.

Pipeline: Gemini Review → Official Docs Research → Supervisor Cross-Check → Consensus
"""
import os
import time
import random
import json
import re
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
from tools.utils.secret_manager import decrypt_value
from tools.strategy.token_governor import token_governor
from tools.strategy.decision_logic import router
from tools.utils.llm_utils import extract_json, clean_llm_response

from tools.infrastructure.config import settings
from tools.design.oracle import DesignOracle

# --- 1. CONFIGURATION ---
GEMINI_MODEL = settings.models.gemini_model
GEMINI_PRO_MODEL = settings.models.gemini_pro_model

# Will be initialized lazily when first needed
_gemini_client = None


def _get_gemini_client():
    """Lazy-initialize the Gemini client so we fail gracefully if key is missing."""
    global _gemini_client
    if _gemini_client is None:
        import dotenv
        from tools.infrastructure.config import discover_env_file
        
        # Robust override: load raw value directly from .env file to bypass any stale env variables
        env_file = discover_env_file()
        raw_key = None
        if os.path.exists(env_file):
            env_vars = dotenv.dotenv_values(env_file)
            raw_key = env_vars.get("GEMINI_API_KEY")
            
        if not raw_key:
            raw_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else None
            
        if not raw_key:
            raise ValueError(
                "❌ GEMINI_API_KEY not found in Sovereign Settings. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        # Handle encrypted keys
        api_key = decrypt_value(raw_key)
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# --- 2. LOW-LEVEL GEMINI HELPER ---
def _call_gemini(
    system_prompt: str, 
    user_message: str, 
    temperature: float = 0.2,
    thinking: bool = False,
    thinking_level: str = "medium",
    search_grounding: bool = False,
    model_override: str = None
) -> str:
    """
    Calls the Gemini API with a system instruction and user message.
    Includes simple retry logic for 429 (Rate Limit) errors.
    """
    client = _get_gemini_client()
    max_retries = 2 # Reduced for faster failover
    base_delay = 5  # Higher initial delay for 429s

    # System 4: Smart Budget & Complexity Enforcement
    if not model_override:
        # 4a. Intelligence Router: Choose model based on complexity/urgency
        smart_model = router.recommend_model(user_message)
        # 4b. Budget Governor: Downgrade if funds are low
        model_to_use = token_governor.get_budget_aware_model(smart_model, task_critical=thinking)
    else:
        model_to_use = token_governor.get_budget_aware_model(model_override, task_critical=thinking)

    # Map our levels to official SDK values
    thinking_config = None
    if thinking:
        thinking_config = types.ThinkingConfig(
            thinking_level=thinking_level.lower() # minimal, low, medium, high
        )

    # Google Search Grounding (Gemini 3 Native)
    tools = []
    if search_grounding:
        tools.append(types.Tool(
            google_search=types.GoogleSearch()
        ))

    start_time = time.time()
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_to_use,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    max_output_tokens=8192,
                    thinking_config=thinking_config,
                    tools=tools if tools else None
                ),
                contents=user_message,
            )
            duration = time.time() - start_time
            cost = 0.0
            # Track usage in TokenGovernor
            try:
                usage = response.usage_metadata
                cost = token_governor.track_usage(
                    model=model_to_use,
                    input_tokens=usage.prompt_token_count,
                    output_tokens=usage.candidates_token_count,
                    task_id="gemini_call"
                )
            except Exception as usage_err:
                print(f"⚠️ Failed to track usage: {usage_err}")

            # Feedback to Multi-Armed Bandit router
            router.record_model_feedback(
                model=model_to_use,
                task=user_message,
                success=True,
                latency=duration,
                cost=cost
            )
            return response.text
        except Exception as e:
            # Robust 429 detection
            err_msg = str(e).upper()
            status_code = getattr(e, "status_code", None)
            
            is_rate_limit = (
                "429" in err_msg or 
                "RESOURCE_EXHAUSTED" in err_msg or 
                "RATE_LIMIT" in err_msg or
                status_code == 429
            )
            
            if is_rate_limit and attempt < max_retries - 1:
                # Exponential backoff with jitter: delay = base * 2^attempt + random_jitter
                sleep_time = (base_delay * (2 ** attempt)) + (random.random() * 2)
                print(f"⚠️ Gemini Rate Limit (429). Quota exhausted. Retrying in {sleep_time:.1f}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
            
            # If it's a different error or we're out of retries
            duration = time.time() - start_time
            router.record_model_feedback(
                model=model_to_use,
                task=user_message,
                success=False,
                latency=duration,
                cost=0.0
            )
            print(f"❌ Gemini Error: {e}")
            raise e


def call_gemini_pro(prompt: str, temperature: float = 0.5) -> str:
    """
    Public wrapper for high-reasoning tasks. 
    Uses the configured GEMINI_MODEL (ideally Gemini 1.5 Pro).
    """
    return _call_gemini(
        system_prompt="You are a high-reasoning AI agent. Process the following request with precision.",
        user_message=prompt,
        temperature=temperature,
        thinking=True, # Pro tasks benefit from thinking
        thinking_level="medium",
        model_override=GEMINI_PRO_MODEL
    )


# --- 3. OFFICIAL DOCS RESEARCH (Shared Helper) ---
def _research_docs(tech_key: str, query: str, registry: dict = None, max_results: int = 3) -> str:
    """
    Searches official docs using Gemini 3 Native Search Grounding.
    This replaces the legacy DuckDuckGo site-search and broken MCP tools.
    """
    print(f"📡 Step 2/4: Researching {tech_key} with Native Search Grounding...")
    
    system_prompt = (
        f"You are a Documentation Researcher specializing in {tech_key}. "
        "Use Google Search to find the most accurate and up-to-date information. "
        "Summarize the findings and provide source links."
    )
    
    search_query = f"official documentation for {tech_key} {query}"
    
    try:
        result = _call_gemini(
            system_prompt=system_prompt,
            user_message=search_query,
            search_grounding=True
        )
        return f"### 📘 Native Search Grounding ({tech_key})\n\n{result}"
    except Exception as e:
        return f"⚠️ Native research failed: {e}"


# --- 4. MAIN PIPELINE: CODE REVIEW ---
def _step_1_initial_review(code_snippet: str, review_context: str, thinking: bool, thinking_level: str) -> str:
    print("🔮 Step 1/4: Gemini reviewing code...")
    system_prompt = (
        "You are a Senior Code Reviewer with 15+ years of experience. "
        "Perform a DEEP REASONING analysis before providing your findings. "
        "Structure your response as follows:\n\n"
        "### 🧠 Reasoning Phase\n"
        "- What is this code trying to achieve?\n"
        "- What are the hidden edge cases?\n"
        "- Are there any 'Architectural Smells'?\n\n"
        "### 🔴 Critical Findings (Security/Stability)\n"
        "- SQL injection, XSS, auth bypasses, exposed secrets\n"
        "- Race conditions or deadlocks\n\n"
        "### 🟡 Optimization & Best Practices\n"
        "- N+1 queries, unnecessary re-renders, memory leaks\n"
        "- Code style, error handling, type safety\n\n"
        "### 🟢 Senior Logic Critique\n"
        "- SOLID principles, separation of concerns\n"
        "- Scalability (Will this work at 1M users?)\n\n"
        "### 🎨 Heritage Design Compliance\n"
        "- Check for adherence to the Heritage tokens (DESIGN.md).\n"
        f"- Constraints: {DesignOracle.get_rules().get('constraints', {}).get('mandates', [])}\n\n"
        "End with a VERDICT: APPROVED ✅ | NEEDS_CHANGES ⚠️ | REJECTED 🔴"
    )
    user_message = f"CONTEXT: {review_context}\n\nCODE:\n```\n{code_snippet}\n```"
    return _call_gemini(system_prompt, user_message, thinking=thinking, thinking_level=thinking_level)

def _step_3_supervisor_check(code_snippet: str, review_context: str, supervisor_fn) -> str:
    print("🧠 Step 3/4: Consulting local Supervisor (System 2)...")
    try:
        return supervisor_fn(
            user_proposal=f"Review this code for security and scalability: {review_context}",
            code_snippet=code_snippet,
            iterative_mode=False,
        )
    except Exception as e:
        return f"⚠️ Supervisor unavailable: {e}"

def _step_4_consensus(gemini_review: str, supervisor_review: str, docs_context: str, code_snippet: str, thinking: bool, thinking_level: str) -> str:
    print("⚖️ Step 4/4: Generating consensus report...")
    system_prompt = (
        "You are a Chief Technology Officer conducting a final review. "
        "You have TWO independent code reviews below. Your job is to:\n"
        "1. Identify points where BOTH reviewers AGREE (high confidence findings)\n"
        "2. Identify DISAGREEMENTS and explain which reviewer is correct and why\n"
        "3. Flag any issues that NEITHER reviewer caught\n"
        "4. Give a FINAL VERDICT: APPROVED ✅ | NEEDS_MINOR_CHANGES 🟡 | REJECTED 🔴\n\n"
        "Be concise. Focus on actionable insights.\n"
        "MANDATORY: Ensure the code complies with the Heritage Design System tokens.\n"
        f"TOKENS: {json.dumps(DesignOracle.get_rules().get('tokens', {}))}"
    )
    consensus_input = (
        f"=== REVIEWER A (Gemini Cloud AI) ===\n{gemini_review}\n\n"
        f"=== REVIEWER B (Local Supervisor) ===\n{supervisor_review}\n\n"
    )
    if docs_context:
        consensus_input += f"=== OFFICIAL DOCS CONTEXT ===\n{docs_context}\n\n"
    consensus_input += f"=== ORIGINAL CODE ===\n```\n{code_snippet}\n```"
    
    return _call_gemini(system_prompt, consensus_input, thinking=thinking, thinking_level=thinking_level)

def gemini_code_review(
    code_snippet: str,
    review_context: str = "",
    tech_key: str = "",
    cross_check: bool = True,
    thinking: bool = False,
    thinking_level: str = "medium",
    official_docs_registry: dict = None,
    supervisor_fn=None,
) -> str:
    """
    Full-pipeline code review:
      Step 1: Gemini reviews the code
      Step 2: (Optional) Research official docs for grounding
      Step 3: (Optional) Local LLM Supervisor cross-check
      Step 4: Gemini produces consensus report
    """
    report_sections = []

    # Step 1: Initial Review
    try:
        gemini_review = _step_1_initial_review(code_snippet, review_context, thinking, thinking_level)
        report_sections.append(f"## 🔮 GEMINI CODE REVIEW\n\n{gemini_review}")
    except Exception as e:
        return f"❌ Gemini review failed: {e}"

    # Step 2: Research
    docs_context = ""
    if tech_key and official_docs_registry:
        search_query = review_context if review_context else f"best practices {tech_key}"
        docs_context = _research_docs(tech_key, search_query, official_docs_registry)
        report_sections.append(f"## 📘 OFFICIAL DOCS RESEARCH\n\n{docs_context}")

    # Step 3: Supervisor Check
    supervisor_review = ""
    if cross_check and supervisor_fn:
        supervisor_review = _step_3_supervisor_check(code_snippet, review_context, supervisor_fn)
        report_sections.append(f"## 🧠 SUPERVISOR (System 2) REVIEW\n\n{supervisor_review}")

    # Step 4: Consensus
    if supervisor_review and "unavailable" not in supervisor_review:
        try:
            consensus = _step_4_consensus(gemini_review, supervisor_review, docs_context, code_snippet, thinking, thinking_level)
            report_sections.append(f"## ⚖️ CONSENSUS REPORT (CTO Final Review)\n\n{consensus}")
        except Exception as e:
            report_sections.append(f"## ⚖️ CONSENSUS REPORT\n\n⚠️ Consensus generation failed: {e}")

    return "\n\n---\n\n".join(report_sections)



# --- 5. STANDALONE RESEARCH ---
def gemini_research(
    query: str,
    tech_key: str = "",
    thinking: bool = False,
    thinking_level: str = "medium",
    official_docs_registry: dict = None,
) -> str:
    """
    Research a topic using Gemini AI, optionally grounded in official docs.

    Args:
        query: The question or topic to research
        tech_key: If provided, also searches official docs for grounding
        official_docs_registry: The OFFICIAL_DOCS dict
    """
    report_sections = []

    # Step 1: Gemini's own knowledge
    print(f"🔮 Gemini researching: {query}")

    system_prompt = (
        "You are a Senior Solutions Architect with deep knowledge of modern software development. "
        "Answer the user's question with:\n"
        "1. A clear, definitive answer\n"
        "2. Code examples where relevant\n"
        "3. Common pitfalls to avoid\n"
        "4. Links to patterns or best practices\n\n"
        "Be precise and practical. Cite specific API methods or config options."
    )

    try:
        gemini_answer = _call_gemini(
            system_prompt, 
            query, 
            temperature=0.3,
            thinking=thinking,
            thinking_level=thinking_level
        )
        report_sections.append(
            f"## 🔮 GEMINI RESEARCH\n\n{gemini_answer}"
        )
    except Exception as e:
        return f"❌ [v2.1] Gemini research failed: {e}"

    # Step 2: Ground in official docs (optional)
    if tech_key and official_docs_registry:
        print(f"📘 Grounding in {tech_key} official docs...")
        docs = _research_docs(tech_key, query, official_docs_registry)
        report_sections.append(docs)

    separator = "\n\n---\n\n"
    return separator.join(report_sections)

def transcribe_audio(audio_path: str, prompt: str = "Transcribe this audio and extract the user's intent.") -> str:
    """
    Uses Gemini 1.5 Flash to transcribe and extract intent from an audio file.
    Supports high-fidelity 'Native Audio' understanding.
    """
    client = _get_gemini_client()
    
    try:
        # Load the audio file
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
            
        # Gemini 1.5 handles audio bytes directly in the content list
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                temperature=0.1,
                system_instruction="You are a Sensory Interpreter for the Kenbun Swarm. Transcribe the audio and convert it into a clear Swarm Objective."
            ),
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                prompt
            ]
        )
        
        return response.text
    except Exception as e:
        print(f"❌ Audio Transcription failed: {e}")
        return f"ERROR: {e}"
