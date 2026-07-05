import json
import os

path = os.path.expanduser("~/Library/Group Containers/group.com.docker/settings.json")
with open(path, "r") as f:
    data = json.load(f)

print(f"Old size: {data.get('diskSizeMiB')}")
data["diskSizeMiB"] = 81920

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print(f"New size: {data.get('diskSizeMiB')}")
