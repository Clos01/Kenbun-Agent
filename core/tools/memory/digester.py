import asyncio
import time
import requests
import logging
from datetime import datetime, timezone
from tools.infrastructure.config import settings

class SystemDigester:
    """
    The 'Digestive System' (System 1.5).
    Runs quietly in the background using a lightweight local LLM to summarize
    recent user sessions, extract core architectural rules, and persist them 
    for the Tier 2 Supervisor (DeepSeek) to evaluate against later.
    """
    def __init__(self):
        self.ollama_url = settings.workers.ollama_url  # Points to host.docker.internal:11434
        self.model = "llama3.2:3b"  # Fast, efficient local model for digestion
        self.interval = 300  # Wake up every 5 minutes
    
    def fetch_recent_telemetry(self) -> str:
        """
        In a full implementation, this fetches the last N records from Honcho 
        or the raw ChromaDB session history. 
        For now, we simulate fetching recent unsynced telemetry.
        """
        # Simulated recent history context
        return (
            "User: 'ok so go to my portable kenbun file and lets start to implement that...'\n"
            "System: 'Drafting Implementation Plan for Portable Kenbun Cognitive Architecture...'\n"
            "System Event: Added host.docker.internal to docker-compose.yml for Mac Passthrough."
        )

    def generate_digest(self, raw_telemetry: str) -> str:
        """Calls the lightweight local LLM to extract meaning from raw telemetry."""
        logging.info(f"🧠 [DIGESTER] Activating {self.model} to digest recent telemetry...")
        prompt = (
            "You are the Background Digester. Your job is to read recent raw logs and extract "
            "ONLY architectural rules, user preferences, and structural decisions. "
            "Ignore conversational fluff. Format as a bulleted list of rules.\n\n"
            f"RAW TELEMETRY:\n{raw_telemetry}"
        )
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }
        
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "No insights generated.")
        except Exception as e:
            logging.error(f"⚠️ [DIGESTER] Failed to digest telemetry: {e}")
            return ""

    def persist_rules(self, rules: str):
        """Saves the distilled rules to the sovereign database."""
        if not rules:
            return
            
        logging.info("💾 [DIGESTER] Persisting distilled rules to ChromaDB/Knowledge Base.")
        try:
            from tools.memory.chroma_db_connect import get_project_collection
            collection = get_project_collection("digested_rules")
            if collection:
                timestamp = datetime.now(timezone.utc).isoformat()
                doc_id = f"rule_digest_{int(time.time())}"
                collection.upsert(
                    ids=[doc_id],
                    documents=[rules],
                    metadatas=[{"source": "digester_loop", "timestamp": timestamp}]
                )
        except Exception as e:
            logging.error(f"⚠️ [DIGESTER] Failed to persist rules: {e}")

    async def digestion_loop(self):
        """The infinite background loop."""
        logging.info(f"🧬 [DIGESTER] Background Digestion Loop started. Interval: {self.interval}s")
        while True:
            await asyncio.sleep(self.interval)
            
            raw_telemetry = self.fetch_recent_telemetry()
            if raw_telemetry:
                digested_rules = self.generate_digest(raw_telemetry)
                if digested_rules:
                    self.persist_rules(digested_rules)

# Global instance
digester_daemon = SystemDigester()
