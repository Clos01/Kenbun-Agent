import json
import sys

# JSON-RPC request for save_to_hivemind
req = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "save_to_hivemind",
        "arguments": {
            "title": "Test Title",
            "content": "Test Content",
            "tags": "test",
            "category": "concepts"
        }
    }
}

# Write request to stdout so we can pipe it
sys.stdout.write(json.dumps(req) + "\n")
