import subprocess
import re
path = "/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-nodes-base@file+packages+nodes-base_@opentelemetry+api@1.9.0_@opentelemetry+exporte_533cec94887d6989e678f9206e9f2eff/node_modules/n8n-nodes-base/dist/nodes/Google/Gmail/v2/GmailV2.node.js"
code = subprocess.check_output(["docker", "exec", "n8n-docker-n8n-1", "cat", path]).decode("utf-8")
matches = re.findall(r"getNodeParameter\(['\"]([^'\"]+)['\"]", code)
print("getNodeParameter calls:", set(matches))
