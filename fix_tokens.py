import json, fcntl, os

path = "/app/brain_health/usage_stats.json"

if not os.path.exists(path):
    print("File not found.")
    exit(1)

with open(path, 'r+') as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    data = json.load(f)
    # Add 2 million tokens
    data['total_input_tokens'] = data.get('total_input_tokens', 0) + 1600000
    data['total_output_tokens'] = data.get('total_output_tokens', 0) + 400000
    f.seek(0)
    json.dump(data, f, indent=2)
    f.truncate()
    fcntl.flock(f, fcntl.LOCK_UN)
print("Tokens restored successfully.")
