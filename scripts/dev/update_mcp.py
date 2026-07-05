import json

path = '~/.gemini/antigravity/mcp_config.json'
with open(path, 'r') as f:
    data = json.load(f)

data['mcpServers']['Kenbun-tools']['env']['CHROMA_HOST'] = '127.0.0.1'
data['mcpServers']['Kenbun-tools']['env']['PC_IP_ADDRESS'] = '127.0.0.1'

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
