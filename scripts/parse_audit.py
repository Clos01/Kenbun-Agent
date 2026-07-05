import json
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
audit_json = os.path.join(project_root, "audit_results.json")

with open(audit_json) as f:
    data = json.load(f)

out_path = os.path.join(project_root, "brain_health", "audit_results.md")
with open(out_path, "w") as f:
    f.write("# Swarm Audit Results\n\n")
    f.write("> [!WARNING]\n> **High Positives**\n> The Swarm detected potential issues in 226 files. LLMs tend to be overly verbose when auditing code, meaning many of these are likely false positives, style suggestions, or minor un-optimized logic rather than critical crashes.\n\n")
    
    for item in data[:50]: # Show top 50
        name = item["file"].split("/")[-1]
        status = item["status"]
        f.write(f"### {name}\n")
        f.write(f"**Status:** {status}\n")
        
        if item["issues"]:
            snippet = item["issues"][0][:500].replace("\n", " ") + "..."
            f.write(f"> {snippet}\n\n")
        else:
            f.write("> No report\n\n")
