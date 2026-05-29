import json
import os
from datetime import datetime
from pathlib import Path

def generate_dashboard():
    from tools.infrastructure.config import settings
    stats_file = settings.BRAIN_HEALTH_DIR / "usage_stats.json"
    
    if not stats_file.exists():
        print("❌ No usage stats found. Start using the swarm to generate data!")
        return

    with open(stats_file, "r") as f:
        stats = json.load(f)

    total_spend = stats.get("total_spend", 0.0)
    from tools.strategy.token_governor import token_governor
    daily_budget = token_governor.daily_budget
    history = stats.get("history", [])
    
    # Calculate daily spend
    today = datetime.now().date().isoformat()
    daily_spend = sum(h["cost"] for h in history if h["timestamp"].startswith(today))
    
    # Model breakdown
    model_stats = {}
    for h in history:
        m = h["model"]
        model_stats[m] = model_stats.get(m, 0.0) + h["cost"]

    # ASCII Dashboard
    print("\n" + "="*50)
    print("🛸 KENBUN BUDGET DASHBOARD")
    print("="*50)
    
    # Progress Bar for Daily Budget
    percent = min(100, int((daily_spend / daily_budget) * 100))
    bar_length = 20
    filled = int(bar_length * (percent / 100))
    bar = "█" * filled + "░" * (bar_length - filled)
    
    print(f"📅 TODAY:      ${daily_spend:.4f} / ${daily_budget:.2f}")
    print(f"📊 PROGRESS:   [{bar}] {percent}%")
    
    print("-" * 50)
    print(f"🌍 LIFETIME:   ${total_spend:.4f}")
    print(f"💰 REMAINING:  ${max(0, daily_budget - daily_spend):.4f}")
    
    print("-" * 50)
    print("🧠 MODEL BREAKDOWN:")
    for model, cost in sorted(model_stats.items(), key=lambda x: x[1], reverse=True):
        print(f" - {model:25}: ${cost:.4f}")
    
    print("=" * 50)
    print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    generate_dashboard()
