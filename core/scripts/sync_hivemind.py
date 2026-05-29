import os
from pathlib import Path
import re
from hivemind_memory.hive_memory import hive_memory

from tools.infrastructure.config import settings

def sync_post_mortems(dev_root: str = None):
    """
    Scans the Dev directory for POST_MORTEM.md files and ingests them into the Hivemind.
    """
    if dev_root is None:
        dev_root = settings.DEV_ROOT
    dev_path = Path(dev_root)
    count = 0
    
    for project in dev_path.iterdir():
        if project.is_dir():
            pm_path = project / "POST_MORTEM.md"
            if pm_path.exists():
                print(f"📖 Ingesting lessons from {project.name}...")
                content = pm_path.read_text()
                
                # Split by sections (assuming ## Goal or ## Bug)
                sections = re.split(r"## ", content)
                for section in sections:
                    if not section.strip(): continue
                    # Extract a "Task" and "Fix" from the section
                    lines = section.strip().split("\n")
                    task = lines[0]
                    fix = "\n".join(lines[1:])
                    
                    hive_memory.ingest_lesson(
                        task=task,
                        fix=fix,
                        project=project.name
                    )
                    count += 1
    
    print(f"✅ Hivemind Sync Complete. Ingested {count} lessons.")

if __name__ == "__main__":
    sync_post_mortems()
