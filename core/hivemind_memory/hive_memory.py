import json
import os
import re
import time
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter
import math

class HiveMemory:
    """
    Sovereign Local Memory using BM25-style keyword correlation.
    Keeps all data 100% local within brain_health/hive_memory.json.
    """
    def __init__(self, memory_dir: str = None):
        if memory_dir is None:
            from tools.infrastructure.config import settings
            self.memory_dir = settings.BRAIN_HEALTH_DIR
        else:
            self.memory_dir = Path(memory_dir)
        
        self.memory_path = self.memory_dir / "hive_memory.json"
        self.data = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if not self.memory_path.exists():
            return []
        try:
            with open(self.memory_path, "r") as f:
                return json.load(f)
        except:
            return []

    def _save(self):
        with open(self.memory_path, "w") as f:
            json.dump(self.data, f, indent=4)

    def ingest_lesson(self, task: str, fix: str, project: str):
        """Adds a new lesson to the local hivemind."""
        entry = {
            "task": task,
            "fix": fix,
            "project": project,
            "timestamp": time.time(),
            "tokens": self._tokenize(task)
        }
        self.data.append(entry)
        self._save()

    def _tokenize(self, text: str) -> List[str]:
        # Simple cleanup and tokenization
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return [t for t in text.split() if len(t) > 2]

    def query(self, task: str, project: str | None = None, limit: int = 3) -> List[Dict[str, Any]]:
        """Finds similar past fixes using keyword correlation and filters by project."""
        query_tokens = self._tokenize(task)
        if not query_tokens:
            return []

        scores = []
        for entry in self.data:
            if project and entry.get("project") != project:
                continue
            entry_tokens = entry.get("tokens", [])
            # Simple Jaccard-style overlap or TF-IDF
            intersection = set(query_tokens).intersection(set(entry_tokens))
            score = len(intersection) / (math.sqrt(len(query_tokens) * len(entry_tokens)) + 1)
            if score > 0.1:
                scores.append((score, entry))

        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scores[:limit]]

# Global Instance
hive_memory = HiveMemory()
