import json
from pathlib import Path
from datetime import datetime

def generate_report():
    benchmarks_path = Path("brain_health/BENCHMARKS.json")
    if not benchmarks_path.exists():
        print("❌ No benchmarks found. Run nightly_eval.py first.")
        return

    try:
        with open(benchmarks_path, "r") as f:
            data = json.load(f)
        
        history = data.get("history", [])
        if len(history) < 1:
            print("❌ Benchmark history is empty.")
            return

        today = history[-1]
        yesterday = history[-2] if len(history) > 1 else None

        # Calculate Deltas
        acc_delta = (today["routing_accuracy"] - yesterday["routing_accuracy"]) if yesterday else 0
        lat_delta = (today["median_latency_ms"] - yesterday["median_latency_ms"]) if yesterday else 0
        
        def format_delta(val, inverse=False):
            if val == 0: return "flat"
            prefix = "▲" if val > 0 else "▼"
            # Latency: lower is better, so flip the 'better' indicator
            better = (val < 0) if inverse else (val > 0)
            color = "better" if better else "regression"
            return f"{prefix} {abs(val):.2%} ({color})"

        report = [
            f"# 📊 Kenbun Daily Intelligence Report — {today['date']}",
            f"**Run Status:** {'Full Sweep' if today['full_sweep'] else 'Partial Audit'} ({today['n_cases']} cases)",
            "",
            "## 📈 Core Metrics",
            f"- **Routing Accuracy:** {today['routing_accuracy']:.2%} ({format_delta(acc_delta)})",
            f"- **Median Latency:**   {today['median_latency_ms']:.2f}ms ({format_delta(lat_delta / 100 if yesterday else 0, inverse=True)})",
            "",
            "## 🗂️ Per-Class Performance"
        ]

        for cls, stats in today["per_class_accuracy"].items():
            report.append(f"- **{cls}**: {stats['accuracy']:.2%} (n={stats['n']})")

        if today.get("top_misses"):
            report.append("\n## 🆕 Top Regressions / Misses")
            for miss in today["top_misses"][:5]:
                report.append(f"- **Task:** `{miss['task']}`")
                report.append(f"  - Expected: `{miss['expected']}` | Got: `{miss['got']}`")

        report.append("\n---")
        report.append(f"*Generated at {datetime.now().strftime('%H:%M:%S')}*")

        # Output to terminal
        print("\n".join(report))
        
        # Also save to a report file
        with open("brain_health/daily_report.md", "w") as f:
            f.write("\n".join(report))

    except Exception as e:
        print(f"❌ Error generating report: {e}")

if __name__ == "__main__":
    generate_report()
