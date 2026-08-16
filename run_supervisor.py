import sys
from pathlib import Path

# Add core to sys.path so we can import the tools
sys.path.insert(0, str(Path("core").resolve()))

from tools.infrastructure.server import consult_supervisor

proposal = "I am performing an additive cross-repository sync from Kenbun to kenbun-agent. I am specifically omitting the --delete flag so that I do not destroy unique files in the target repository like AI_POLICY.md and DILIGENCE.md. Does this rsync command look safe?"
snippet = "rsync -av --exclude=.git --exclude=.venv --exclude=node_modules --exclude=__pycache__ --exclude=.next --exclude=postgres_data --exclude=chroma_data --exclude=.gemini /Users/carlosrivas/Dev/Kenbun/ /Users/carlosrivas/Dev/kenbun-agent/"

try:
    print(consult_supervisor(proposal, snippet, False))
except Exception as e:
    print(f"Error: {e}")

