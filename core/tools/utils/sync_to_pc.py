import os
import subprocess
from pathlib import Path
from tools.infrastructure.config import settings

# --- CONFIGURATION ---
PROJECT_ROOT = settings.PROJECT_ROOT
PC_IP = settings.SWARM_PC_IP
PC_USER = settings.deployment.pc_user
REMOTE_PATH = settings.deployment.pc_remote_path
SSH_KEY_PATH = settings.deployment.ssh_key_path
LOCAL_DATA_DIR = PROJECT_ROOT / "training_data"

def sync():
    print(f"📡 Preparing to sync Kenbun Intelligence to PC ({PC_IP})...")
    
    if not PC_IP:
        print("❌ Error: PC_IP_ADDRESS not found in .env")
        return

    if not LOCAL_DATA_DIR.exists():
        print(f"❌ Error: {LOCAL_DATA_DIR} does not exist. Run harvester.py first.")
        return

    # Use SCP to push the directory to the PC
    # Now using the specific Kenbun SSH key for password-less sync
    try:
        print(f"🚀 Pushing training data to {PC_USER}@{PC_IP}...")
        
        # Ensure remote directory exists
        mkdir_cmd = f"ssh -i {SSH_KEY_PATH} {PC_USER}@{PC_IP} 'mkdir -p {REMOTE_PATH}'"
        subprocess.run(mkdir_cmd, shell=True, check=True)
        
        # Sync files
        sync_cmd = f"scp -i {SSH_KEY_PATH} -r {LOCAL_DATA_DIR}/* {PC_USER}@{PC_IP}:{REMOTE_PATH}"
        subprocess.run(sync_cmd, shell=True, check=True)
        
        print(f"✅ SUCCESS: Intelligence synced to {PC_USER}@{PC_IP}:{REMOTE_PATH}")
        print(f"👉 Next Step: Run training scripts on your PC in the {REMOTE_PATH} folder.")
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Sync Failed: {e}")
        print("\n🔍 Troubleshooting:")
        print(f"1. Make sure your PC is at {PC_IP}")
        print("2. Make sure SSH is enabled on your PC (run 'sudo apt install openssh-server' in WSL)")
        print(f"3. Make sure you can 'ssh {PC_USER}@{PC_IP}' from this Mac.")

if __name__ == "__main__":
    sync()
