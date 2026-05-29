import os
import json
import subprocess
import time
from pathlib import Path

from tools.infrastructure.config import settings

# --- CONFIGURATION ---
TRAINING_DIR = Path(settings.TRAINING_DIR) # Inside Docker path
HOST_TRAINING_DIR = Path(settings.PC_REMOTE_PATH).expanduser() # Outside Docker path
DATASET_FILE = HOST_TRAINING_DIR / "kenbun_dataset.jsonl"
INCOMING_FILE = HOST_TRAINING_DIR / "incoming_lessons.jsonl"

def run_step(command, description):
    print(f"🚀 [STEP] {description}...")
    try:
        subprocess.run(command, shell=True, check=True, cwd=HOST_TRAINING_DIR)
        print(f"✅ {description} Complete.")
    except Exception as e:
        print(f"❌ {description} FAILED: {e}")
        return False
    return True

def nightly_bake():
    print("🌙 --- NIGHTLY NEURAL BAKE INITIATED ---")
    
    # 1. Merge incoming lessons
    if INCOMING_FILE.exists():
        print(f"📈 Merging new lessons from {INCOMING_FILE}...")
        with open(INCOMING_FILE, "r") as f_in, open(DATASET_FILE, "a") as f_out:
            f_out.write(f_in.read())
        # Clear the incoming file
        INCOMING_FILE.unlink()
    else:
        print("💤 No new lessons found. Skipping bake.")
        return

    # 2. Run Training (Unsloth)
    if not run_step("python3 train_brain.py", "Neural Re-Baking (15 Steps)"):
        return

    # 3. Run Export (GGUF)
    if not run_step("python3 export_brain.py", "GGUF Export & Quantization"):
        return

    # 4. Reload Docker Container
    print("🔄 Reloading Neural Hub...")
    run_step("docker exec -it ollama ollama create antigrav -f /root/kenbun_training/Modefile", "Ollama Brain Update")

    print("🏆 --- NIGHTLY BAKE SUCCESSFUL. BRAIN IS EVOLVED. ---")

if __name__ == "__main__":
    nightly_bake()
