import json

path = '/Users/carlosrivas/.gemini/antigravity/mcp_config.json'
with open(path, 'r') as f:
    data = json.load(f)

data['mcpServers']['Kenbun-tools']['env']['CHROMA_HOST'] = '100.120.241.65'
data['mcpServers']['Kenbun-tools']['env']['PC_IP_ADDRESS'] = '100.120.241.65'

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
