from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional
import json

# --- PATH SETUP ---
from tools.infrastructure.config import settings
DB_PATH = settings.INTELLIGENCE_DB_PATH
LOG_FILE = settings.BRAIN_HEALTH_DIR / "swarm_voice.log"
DATASET_FILE = settings.PROJECT_ROOT / "core" / "training_data" / "kenbun_dataset.jsonl"

app = FastAPI(title="Kenbun Neural Telemetry")

# Enable CORS for the Next.js dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to localhost:3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ToolStat(BaseModel):
    tool_id: str
    category: Optional[str]
    alpha: float
    beta: float
    success_count: int
    failure_count: int
    success_rate: float
    confidence: str

@app.get("/stats", response_model=List[ToolStat])
async def get_stats():
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database not found")
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    cursor.execute("SELECT tool_id, category, alpha, beta, success_count, failure_count FROM intelligence")
    rows = cursor.fetchall()
    conn.close()
    
    stats = []
    for row in rows:
        tool_id, category, alpha, beta, success, failure = row
        total = alpha + beta
        success_rate = (alpha / total) if total > 0 else 0
        
        # Simple confidence metric
        import math
        variance = (alpha * beta) / (total**2 * (total + 1)) if total > 0 else 1
        std_dev = math.sqrt(variance)
        confidence = "HIGH" if std_dev < 0.05 else "MEDIUM" if std_dev < 0.15 else "LOW"
        
        stats.append(ToolStat(
            tool_id=tool_id,
            category=category,
            alpha=alpha,
            beta=beta,
            success_count=success,
            failure_count=failure,
            success_rate=success_rate,
            confidence=confidence
        ))
    return stats

@app.get("/logs")
async def get_logs(lines: int = 50):
    if not LOG_FILE.exists():
        return {"logs": ["Log file not found."]}
    
    try:
        with open(LOG_FILE, "r") as f:
            content = f.readlines()
            return {"logs": content[-lines:]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/dataset")
async def get_dataset(limit: int = 5):
    if not DATASET_FILE.exists():
        return {"error": "Dataset not found"}
    
    samples = []
    with open(DATASET_FILE, "r") as f:
        for i, line in enumerate(f):
            if i >= limit: break
            samples.append(json.loads(line))
    return {"samples": samples}

@app.get("/benchmarks")
async def get_benchmarks():
    benchmark_path = settings.PROJECT_ROOT / "brain_health" / "BENCHMARKS.json"
    if not benchmark_path.exists():
        return {"error": "Benchmarks not found"}
    
    with open(benchmark_path, "r") as f:
        return json.load(f)

@app.get("/training_status")
async def get_training_status():
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        return {"status": "IDLE", "message": "No active training detected"}
    
    # Check for latest checkpoint
    checkpoints = sorted([d for d in os.listdir(outputs_dir) if d.startswith("checkpoint")], reverse=True)
    if not checkpoints:
        return {"status": "INITIALIZING", "message": "Starting training process..."}
    
    latest = outputs_dir / checkpoints[0] / "trainer_state.json"
    if latest.exists():
        with open(latest, "r") as f:
            return {"status": "TRAINING", "data": json.load(f)}
            
    return {"status": "TRAINING", "message": f"Currently at {checkpoints[0]}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.MONITOR_PORT)
