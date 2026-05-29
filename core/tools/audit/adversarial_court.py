"""
System 2a: Adversarial LLM Auditing Court.
Establishes a rigorous, adversarial code validation trial consisting of:
1. The Defendant Counsel: Defends the generated code's design and safety.
2. The Prosecuting Auditor: Acts as a red-team critic finding security traversal/injection risks.
3. The Presiding Judge: Weighs both cases and issues a final binding APPROVED/REJECTED verdict.
"""
import os
import sys
import json
import time
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from pathlib import Path

from tools.infrastructure.config import settings
from tools.utils.llm_utils import extract_json
from tools.infrastructure.topology_manager import log_swarm_event

class AdversarialCourt:
    def __init__(self):
        self.log_dir = Path(settings.BRAIN_HEALTH_DIR)
        self.log_file = "court_history.jsonl"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    @property
    def full_log_path(self) -> Path:
        return self.log_dir / self.log_file

    async def _query_llm(self, system_prompt: str, user_prompt: str, role: str) -> str:
        """Helper to route and execute a chat request to the primary LLM provider."""
        url = settings.PRIMARY_LLM_URL.rstrip('/')
        model = settings.PRIMARY_LLM_MODEL

        # Handle direct Ollama chat endpoint if applicable
        if "11434" in url or "ollama" in url:
            chat_url = f"{url}/api/chat" if not url.endswith("/v1") else f"{url.replace('/v1', '')}/api/chat"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.2 if role != "prosecutor" else 0.4}
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(chat_url, json=payload, timeout=45) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data['message']['content']
            except Exception as e:
                # Fallback to standard OpenAI compatible route
                pass

        # Standard OpenAI compatible client routing (via llm_router compatible format)
        from tools.utils.llm_router import call_llm_gateway
        try:
            response = await asyncio.to_thread(
                call_llm_gateway,
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.3
            )
            if response:
                return response
        except Exception:
            pass

        return f"Error: Failed to fetch response from LLM for role: {role}."

    async def run_trial(self, proposal: str, code_snippet: str) -> Dict[str, Any]:
        """Runs the complete adversarial court trial asynchronously."""
        start_time = time.time()
        
        # Color definitions for terminal transcript outputs
        PINK = "\033[38;5;218m"
        ROSE = "\033[38;5;224m"
        GRAY = "\033[38;5;246m"
        YELLOW = "\033[38;5;226m"
        CYAN = "\033[38;5;38m"
        RED = "\033[38;5;196m"
        GREEN = "\033[38;5;46m"
        NC = "\033[0m"
        BOLD = "\033[1m"

        print(f"\n{PINK}{BOLD}🏛️  [KENBUN LLM ADVERSARIAL COURT] Convening trial session...{NC}")
        print(f"{GRAY}Proposal: {proposal}{NC}\n")

        # --- STEP 1: DEFENDANT ---
        print(f"🔹 {CYAN}[COURT] Calling Defendant's Counsel to justify the proposal...{NC}")
        defendant_system = (
            "You are the Defendant's Counsel. Your client is an AI agent that generated a code block to satisfy a user request. "
            "Defend the safety, optimization, and correctness of this code. Provide a solid argument on why this code "
            "poses zero security risks, avoids remote command injections, and handles relative path boundaries perfectly."
        )
        defendant_user = f"PROPOSAL: {proposal}\n\nCODE TO DEFEND:\n{code_snippet}"
        
        defendant_arg = await self._query_llm(defendant_system, defendant_user, "defendant")
        print(f"  {ROSE}➔ Defendant's Justification Brief compiled.{NC}")

        # --- STEP 2: PROSECUTOR ---
        print(f"🔹 {RED}[COURT] Calling Prosecuting Security Critic to find vulnerabilities...{NC}")
        prosecutor_system = (
            "You are the Prosecuting Security Auditor. Your objective is to find hidden security flaws, traversal exploits, "
            "remote execution injection holes, syntax errors, or logical bugs in the proposed code snippet. "
            "Provide a critical, highly suspicious indictment outlining the exact line numbers and risks."
        )
        prosecutor_user = f"PROPOSAL: {proposal}\n\nCODE TO INDICT:\n{code_snippet}"
        
        prosecution_arg = await self._query_llm(prosecutor_system, prosecutor_user, "prosecutor")
        print(f"  {YELLOW}➔ Prosecution's Indictment Brief compiled.{NC}")

        # --- STEP 3: THE JUDGE ---
        print(f"🔹 {PINK}[COURT] Presiding Judge weighing arguments and rendering Verdict...{NC}")
        judge_system = (
            "You are the presiding Judge of the Kenbun security court. You have been presented with a code snippet, "
            "a Defendant Counsel's argument for its safety, and a Prosecuting Auditor's indictment of security risks. "
            "Critically review both arguments. Weigh the evidence and issue a final, binding Verdict. "
            "You must return ONLY a JSON block containing: \n"
            "{\n"
            "  \"verdict\": \"APPROVED\" or \"REJECTED\",\n"
            "  \"confidence\": 0.0 to 1.0,\n"
            "  \"critique\": \"A summary explaining your legal reasoning, weighing both briefs.\"\n"
            "}"
        )
        judge_user = (
            f"PROPOSAL: {proposal}\n\n"
            f"CODE SNIPPET:\n{code_snippet}\n\n"
            f"DEFENSE BRIEF:\n{defendant_arg}\n\n"
            f"PROSECUTION BRIEF:\n{prosecution_arg}"
        )
        
        judge_raw = await self._query_llm(judge_system, judge_user, "judge")
        judge_parsed = extract_json(judge_raw)

        if not judge_parsed:
            # Fallback parsing in case JSON is corrupted
            verdict = "APPROVED" if "APPROV" in judge_raw.upper() else "REJECTED"
            judge_parsed = {
                "verdict": verdict,
                "confidence": 0.5,
                "critique": f"Fallback: Failed to parse Judge JSON. Raw response: {judge_raw[:300]}"
            }

        verdict = judge_parsed.get("verdict", "REJECTED").upper()
        confidence = float(judge_parsed.get("confidence", 0.5))
        critique = judge_parsed.get("critique", "No critique provided.")

        # --- PRINT COURT TRANSCRIPT ---
        print(f"\n{PINK}{BOLD}┌─────────────────────────────────────────────────────────┐")
        print(f"│              ⚖️  OFFICIAL COURT TRANSCRIPT               │")
        print(f"├─────────────────────────────────────────────────────────┤{NC}")
        
        # Format and truncate Defendant brief
        def_lines = [line.strip() for line in defendant_arg.split("\n") if line.strip()][:3]
        print(f"  {CYAN}{BOLD}[DEFENSE BRIEFS]{NC}")
        for line in def_lines:
            print(f"    {c_g if 'c_g' in locals() else GRAY}➔ {line[:70]}...{NC}")
        print("")
        
        # Format and truncate Prosecution brief
        pros_lines = [line.strip() for line in prosecution_arg.split("\n") if line.strip()][:3]
        print(f"  {RED}{BOLD}[PROSECUTION BRIEFS]{NC}")
        for line in pros_lines:
            print(f"    {c_g if 'c_g' in locals() else GRAY}➔ {line[:70]}...{NC}")
        print("")

        # Render Judge Verdict Callout Box
        v_color = GREEN if verdict == "APPROVED" else RED
        print(f"  {PINK}{BOLD}[JUDGE VERDICT]{NC}")
        print(f"    {BOLD}Verdict:    {v_color}{verdict}{NC}")
        print(f"    {BOLD}Confidence: {CYAN}{confidence * 100:.1f}%{NC}")
        print(f"    {BOLD}Ruling:     {ROSE}{critique}{NC}")
        print(f"{PINK}{BOLD}└─────────────────────────────────────────────────────────┘{NC}\n")

        # Record to history
        court_entry = {
            "timestamp": time.time(),
            "proposal": proposal,
            "verdict": verdict,
            "confidence": confidence,
            "critique": critique,
            "defendant_argument": defendant_arg,
            "prosecution_argument": prosecution_arg,
            "duration_seconds": time.time() - start_time
        }
        self._log_court(court_entry)

        # Notify Swarm topology manager
        log_swarm_event("DECISION", {
            "tool": "adversarial_court",
            "confidence": confidence,
            "result": verdict,
            "logic": f"Judge Verdict: {verdict} ({confidence*100:.1f}%). Critique: {critique}",
            "output": critique
        })

        return court_entry

    def _log_court(self, entry: Dict[str, Any]):
        try:
            with open(self.full_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"⚠️ Failed to log adversarial court entry: {e}")

# Global instance
adversarial_court = AdversarialCourt()
