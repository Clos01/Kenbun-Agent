import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any
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
        except Exception:
            return []

    def _save(self):
        with open(self.memory_path, "w") as f:
            json.dump(self.data, f, indent=4)

    def ingest_lesson(self, task: str, fix: str, project: str):
        """Adds a new lesson to the local hivemind with strict atomic file locking."""
        try:
            try:
                import fcntl
            except ImportError:
                fcntl = None
            try:
                import msvcrt
            except ImportError:
                msvcrt = None

            with open(self.memory_path, "a+") as f:
                # 1. Acquire exclusive lock to block all other agents
                if fcntl:
                    fcntl.flock(f, fcntl.LOCK_EX)
                elif msvcrt:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    # 2. Reload absolute latest state from disk while locked
                    f.seek(0)
                    content = f.read()
                    data = json.loads(content) if content else []
                except Exception:
                    data = []
                    
                # 3. Append our new knowledge
                entry = {
                    "task": task,
                    "fix": fix,
                    "project": project,
                    "timestamp": time.time(),
                    "tokens": self._tokenize(task)
                }
                data.append(entry)
                
                # 4. Truncate and rewrite atomic state
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=4)
                
                # 5. Release lock
                if fcntl:
                    fcntl.flock(f, fcntl.LOCK_UN)
                elif msvcrt:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                
            # 6. Update in-memory reference
            self.data = data
        except Exception as e:
            print(f"[HIVE_MEMORY_ERROR] Failed to ingest lesson atomically: {e}")

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
        # Protect against O(N) algorithmic complexity collapse by limiting to 1000 recent lessons
        for entry in self.data[-1000:]:
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
