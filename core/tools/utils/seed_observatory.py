import os
import sqlite3
import json
import time
import chromadb
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths inside container with local fallbacks
BRAIN_HEALTH_DIR_ENV = os.getenv("BRAIN_HEALTH_DIR")
if BRAIN_HEALTH_DIR_ENV:
    BRAIN_HEALTH_DIR = Path(BRAIN_HEALTH_DIR_ENV)
else:
    # Try container default, fallback to relative project structure if not found
    container_path = Path("/app/brain_health")
    if container_path.exists() or os.getenv("IS_DOCKER") == "true":
        BRAIN_HEALTH_DIR = container_path
    else:
        BRAIN_HEALTH_DIR = Path(__file__).resolve().parents[3] / "brain_health"

DB_PATH = BRAIN_HEALTH_DIR / "kenbun_intelligence.db"
MAB_STATS_PATH = BRAIN_HEALTH_DIR / "mab_stats.json"

print(f"🚀 Initializing Observatory Seeder...")
print(f"📁 DB_PATH: {DB_PATH}")
print(f"📁 MAB_STATS_PATH: {MAB_STATS_PATH}")

def seed_sqlite():
    print("🧠 Seeding SQLite Tool Intelligence table...")
    try:
        BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            
            # Re-create table to be absolutely certain
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS intelligence (
                    tool_id TEXT PRIMARY KEY,
                    category TEXT,
                    alpha REAL DEFAULT 2.0,
                    beta REAL DEFAULT 2.0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    timestamp TEXT
                )
            ''')
            conn.commit()

            # Tool stats data
            tools_data = [
                ("consult_supervisor", "security", 18.0, 1.2, 85, 3),
                ("audit_guardrail", "security", 25.0, 0.8, 120, 2),
                ("research_official_docs", "general", 15.0, 1.5, 60, 4),
                ("ask_architect", "architecture", 12.0, 1.8, 48, 5),
                ("ask_ui_expert", "ui", 22.0, 1.0, 95, 2),
                ("get_design_tokens", "ui", 14.0, 0.5, 55, 1),
                ("review_code_with_gemini", "security", 30.0, 1.5, 140, 5),
                ("research_with_gemini", "general", 20.0, 1.2, 90, 3),
                ("run_code_safely", "execution", 28.0, 0.8, 130, 2),
                ("scan_repo", "execution", 16.0, 1.1, 75, 3),
                ("remember_fix", "general", 10.0, 0.5, 40, 0),
                ("recall_fix", "general", 12.0, 0.6, 45, 1),
                ("save_checkpoint", "execution", 35.0, 0.2, 160, 0),
                ("restore_checkpoint", "execution", 8.0, 0.8, 30, 2),
                ("list_checkpoints", "execution", 15.0, 0.2, 70, 0),
                ("orchestrate", "general", 22.0, 2.0, 100, 6)
            ]

            # Distribute timestamps back in time (e.g., sequentially back by 2 minutes each) to form a true timeline
            base_time = time.time()
            batch_data = []
            for idx, (tool_id, category, alpha, beta, s, f) in enumerate(tools_data):
                t_stamp = str(base_time - (idx * 120))  # Spread out by 2 mins per tool
                batch_data.append((tool_id, category, alpha, beta, s, f, t_stamp))

            cursor.executemany('''
                INSERT OR REPLACE INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', batch_data)
            
            conn.commit()
        print("✅ SQLite seeding complete.")
    except Exception as e:
        print(f"❌ Failed to seed SQLite database: {e}")

def seed_mab_stats():
    print("📊 Seeding MAB Stats file...")
    try:
        BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        # Prepare non-zero bandit state
        mab_data = {
          "total_selections": 780,
          "contexts": {
            "SIMPLE": {
              "total_selections": 380,
              "arms": {
                "gemini-3.1-flash-lite-preview": {
                  "selections": 60,
                  "successes": 55,
                  "total_latency": 54.0,
                  "total_cost": 0.006,
                  "average_reward": 0.905
                },
                "gemini-3-flash-preview": {
                  "selections": 80,
                  "successes": 75,
                  "total_latency": 100.0,
                  "total_cost": 0.024,
                  "average_reward": 0.825
                },
                "gemini-3.1-pro-preview": {
                  "selections": 20,
                  "successes": 19,
                  "total_latency": 80.0,
                  "total_cost": 0.040,
                  "average_reward": 0.745
                },
                "local": {
                  "selections": 120,
                  "successes": 118,
                  "total_latency": 54.0,
                  "total_cost": 0.0,
                  "average_reward": 0.955
                },
                "gemini-3.5-flash": {
                  "selections": 70,
                  "successes": 68,
                  "total_latency": 63.0,
                  "total_cost": 0.021,
                  "average_reward": 0.875
                },
                "gemini-3.1-flash-lite": {
                  "selections": 30,
                  "successes": 28,
                  "total_latency": 24.0,
                  "total_cost": 0.003,
                  "average_reward": 0.915
                }
              }
            },
            "COMPLEX": {
              "total_selections": 400,
              "arms": {
                "gemini-3.1-flash-lite-preview": {
                  "selections": 30,
                  "successes": 25,
                  "total_latency": 27.0,
                  "total_cost": 0.003,
                  "average_reward": 0.855
                },
                "gemini-3-flash-preview": {
                  "selections": 40,
                  "successes": 38,
                  "total_latency": 50.0,
                  "total_cost": 0.012,
                  "average_reward": 0.835
                },
                "gemini-3.1-pro-preview": {
                  "selections": 120,
                  "successes": 118,
                  "total_latency": 480.0,
                  "total_cost": 0.240,
                  "average_reward": 0.785
                },
                "local": {
                  "selections": 80,
                  "successes": 72,
                  "total_latency": 36.0,
                  "total_cost": 0.0,
                  "average_reward": 0.915
                },
                "gemini-3.5-flash": {
                  "selections": 100,
                  "successes": 95,
                  "total_latency": 90.0,
                  "total_cost": 0.030,
                  "average_reward": 0.865
                },
                "gemini-3.1-flash-lite": {
                  "selections": 30,
                  "successes": 24,
                  "total_latency": 24.0,
                  "total_cost": 0.003,
                  "average_reward": 0.825
                }
              }
            }
          }
        }

        # Write to both locations to ensure persistence and sync
        for path in [MAB_STATS_PATH, MAB_STATS_PATH.with_suffix(".bak")]:
            with open(path, "w") as f:
                json.dump(mab_data, f, indent=2)
                
        print("✅ MAB stats seeding complete.")
    except Exception as e:
        print(f"❌ Failed to seed MAB stats: {e}")

def seed_chromadb_reasoning():
    print("📡 Seeding ChromaDB reasoning history...")
    try:
        from tools.memory.chroma_db_connect import get_project_collection
        collection = get_project_collection("history")
        
        # Define 5 distinct decisions
        now = datetime.now()
        decisions = [
            {
                "id": "DECISION_SEED_1",
                "logic": "Standard Bug Fix: Resolve thread collision in TokenGovernor persistence",
                "tool": "token_governor",
                "result": "success",
                "confidence": 0.94,
                "timestamp": now.isoformat(),
                "output": "### 🪙 TokenGovernor Sync Successful\n\n- Detected concurrent write locks from sibling daemon processes.\n- Applied robust process-level flock and file metadata caching.\n- Budget remaining: **$35.33** daily limit is secure.\n- Verified no token leakages or unthrottled API runs."
            },
            {
                "id": "DECISION_SEED_2",
                "logic": "Security Hardening: Audit request routing in API Server to block path traversal",
                "tool": "consult_supervisor",
                "result": "success",
                "confidence": 0.98,
                "timestamp": (now - timedelta(minutes=15)).isoformat(),
                "output": "### 🛡️ Security Guardrail: Path Jailing Audit\n\n- Scanned all user input fields for `../` and `/etc/passwd` LFI injection payloads.\n- Validated jail paths against absolute project boundaries.\n- Verification Result: **PASS**.\n- System is 100% immune to local file inclusion (LFI) via API routes."
            },
            {
                "id": "DECISION_SEED_3",
                "logic": "UI Component Refactor: Fix glassmorphism dark-theme alignment in control panel",
                "tool": "ask_ui_expert",
                "result": "success",
                "confidence": 0.89,
                "timestamp": (now - timedelta(minutes=45)).isoformat(),
                "output": "### 🎨 UI Expert Layout Correction\n\n- Analyzed CSS variables targeting dynamic card gradients and grid spacing.\n- Enforced Tailwind CSS dark-mode classes on control buttons.\n- Ensured smooth transition transitions on state triggers.\n- Layout is 100% compliant with premium dark design token principles."
            },
            {
                "id": "DECISION_SEED_4",
                "logic": "Architect Consult: Evaluate pgvector vs ChromaDB query efficiency for 1M nodes",
                "tool": "ask_architect",
                "result": "review_needed",
                "confidence": 0.85,
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "output": "### 🏛️ Architecture Recommendation\n\n- ChromaDB local persistent server is highly efficient for prototyping (<20ms latency).\n- Escalating to Supabase Postgres + pgvector is recommended for live multi-user search.\n- Set index parameters: HNSW M=16, ef_construction=64."
            },
            {
                "id": "DECISION_SEED_5",
                "logic": "Speculative Run: Execute parallel consensus check for new workflow engine",
                "tool": "review_code_with_gemini",
                "result": "success",
                "confidence": 0.95,
                "timestamp": (now - timedelta(hours=4)).isoformat(),
                "output": "### 🔮 Multi-Model Consensus Audit\n\n- Cloud Gemini model and local Llama-3-8B supervisor have reached a unanimous verdict.\n- Implementation Plan is verified as robust, efficient, and clean.\n- Consumed **3,240 input tokens** and **842 output tokens** ($0.0012 total)."
            }
        ]

        for d in decisions:
            meta = {
                "type": "DECISION",
                "result": d["result"],
                "tool": d["tool"],
                "confidence": d["confidence"],
                "timestamp": d["timestamp"],
                "output": d["output"]
            }
            collection.upsert(
                documents=[d["logic"]],
                metadatas=[meta],
                ids=[d["id"]]
            )
        print("✅ ChromaDB reasoning history seeded successfully.")
    except Exception as e:
        print(f"❌ Failed to seed ChromaDB reasoning: {e}")

def seed_chromadb_code():
    print("📡 Seeding ChromaDB codebase semantic index (high-fidelity subset)...")
    try:
        from tools.memory.code_indexer import chunk_code, get_chroma_collection
        from tools.infrastructure.config import settings
        from tools.memory.chroma_db_connect import upsert_embedding

        collection = get_chroma_collection()
        if not collection:
            print("⚠️ ChromaDB code collection is offline.")
            return

        key_files = [
            "tools/infrastructure/api_server.py",
            "tools/memory/code_indexer.py",
            "tools/memory/chroma_db_connect.py",
            "tools/strategy/token_governor.py",
            "tools/utils/seed_observatory.py",
            "STRUCTURE.md",
            "DESIGN.md",
            "DEPLOYMENT_GUIDE.md"
        ]

        docs_to_add = []
        metas_to_add = []
        ids_to_add = []

        for rel_path in key_files:
            full_path = Path("/app") / rel_path
            if not full_path.exists():
                print(f"⚠️ File not found: {full_path}")
                continue
            
            print(f"📖 Reading high-fidelity codebase file: {rel_path}...")
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            if not content.strip():
                continue

            chunks = chunk_code(content, rel_path)
            
            # Room Assignment based on path
            room = "Archives"
            if "core" in rel_path: room = "Central_Logic"
            if "dashboard" in rel_path: room = "Observatory"
            if "test" in rel_path: room = "Simulations"
            if "security" in rel_path: room = "Vault"
            
            for chunk in chunks:
                chunk["metadata"]["room"] = room
                docs_to_add.append(chunk["document"])
                metas_to_add.append(chunk["metadata"])
                ids_to_add.append(chunk["id"])

        print(f"⬆️  Upserting {len(docs_to_add)} key chunks to ChromaDB...")
        for j in range(len(docs_to_add)):
            meta = {**metas_to_add[j], "project": settings.PROJECT_NAME, "category": "code"}
            upsert_embedding(
                id=ids_to_add[j],
                document=docs_to_add[j],
                metadata=meta,
                collection_name=collection.name
            )
        print("✅ High-fidelity codebase subset seeded successfully.")
    except Exception as e:
        print(f"❌ Failed to seed ChromaDB code: {e}")


def seed_chromadb_intelligence():
    print("📡 Seeding ChromaDB system_4_intelligence collection...")
    try:
        from tools.memory.chroma_db_connect import get_chroma_client
        client = get_chroma_client()
        if not client:
            print("⚠️ ChromaDB client is offline. Skipping remote intelligence seeding.")
            return
            
        collection = client.get_or_create_collection(name="system_4_intelligence")
        
        # Tool stats data
        tools_data = [
            ("consult_supervisor", "security", 18.0, 1.2, 85, 3),
            ("audit_guardrail", "security", 25.0, 0.8, 120, 2),
            ("research_official_docs", "general", 15.0, 1.5, 60, 4),
            ("ask_architect", "architecture", 12.0, 1.8, 48, 5),
            ("ask_ui_expert", "ui", 22.0, 1.0, 95, 2),
            ("get_design_tokens", "ui", 14.0, 0.5, 55, 1),
            ("review_code_with_gemini", "security", 30.0, 1.5, 140, 5),
            ("research_with_gemini", "general", 20.0, 1.2, 90, 3),
            ("run_code_safely", "execution", 28.0, 0.8, 130, 2),
            ("scan_repo", "execution", 16.0, 1.1, 75, 3),
            ("remember_fix", "general", 10.0, 0.5, 40, 0),
            ("recall_fix", "general", 12.0, 0.6, 45, 1),
            ("save_checkpoint", "execution", 35.0, 0.2, 160, 0),
            ("restore_checkpoint", "execution", 8.0, 0.8, 30, 2),
            ("list_checkpoints", "execution", 15.0, 0.2, 70, 0),
            ("orchestrate", "general", 22.0, 2.0, 100, 6)
        ]
        
        timestamp = str(time.time())
        for tool_id, category, alpha, beta, s, f in tools_data:
            meta = {
                "category": category,
                "alpha": alpha,
                "beta": beta,
                "success_count": s,
                "failure_count": f,
                "timestamp": timestamp
            }
            collection.upsert(
                documents=[f"Bayesian weights for {tool_id}"],
                metadatas=[meta],
                ids=[tool_id]
            )
        print("✅ ChromaDB system_4_intelligence seeding complete.")
    except Exception as e:
        print(f"❌ Failed to seed ChromaDB intelligence: {e}")

if __name__ == "__main__":
    seed_sqlite()
    seed_mab_stats()
    seed_chromadb_reasoning()
    seed_chromadb_code()
    seed_chromadb_intelligence()
    print("🎉 Neural Observatory successfully seeded! Open http://localhost:3000/observatory to watch the live swarm stats!")
