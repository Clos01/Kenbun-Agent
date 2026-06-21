import yaml

with open("docker-compose.remote.yml", "r") as f:
    text = f.read()

data = yaml.safe_load(text)

header = []
for line in text.splitlines():
    if line.startswith("#") or line.strip() == "":
        header.append(line)
    else:
        break

tailscale = {
    "image": "tailscale/tailscale:latest",
    "container_name": "tailscale",
    "environment": ["TS_AUTHKEY=${TS_AUTHKEY?Required}", "TS_STATE_DIR=/var/lib/tailscale"],
    "volumes": ["./tailscale-state:/var/lib/tailscale"],
    "cap_add": ["net_admin", "net_raw"],
    "restart": "unless-stopped"
}

new_services = {"tailscale": tailscale}

for svc_name, svc in data["services"].items():
    if svc_name == "tailscale": continue
    
    svc["network_mode"] = "service:tailscale"
    
    if "ports" in svc: del svc["ports"]
    if "networks" in svc: del svc["networks"]
        
    deps = svc.get("depends_on", {})
    if isinstance(deps, list):
        deps.append("tailscale")
    else:
        deps["tailscale"] = {"condition": "service_started"}
    svc["depends_on"] = deps
    
    if "environment" in svc:
        env = svc["environment"]
        if isinstance(env, list):
            new_env = []
            for e in env:
                e = e.replace("CHROMA_HOST=chromadb", "CHROMA_HOST=localhost")
                e = e.replace("OLLAMA_HOST=ollama_server:11434", "OLLAMA_HOST=localhost:11434")
                e = e.replace("ASSEMBLY_PC_IP=ollama_server", "ASSEMBLY_PC_IP=localhost")
                e = e.replace("PRIMARY_LLM_URL=http://ollama_server:11434/v1", "PRIMARY_LLM_URL=http://localhost:11434/v1")
                e = e.replace("OLLAMA_URL=http://ollama_server:11434/api/generate", "OLLAMA_URL=http://localhost:11434/api/generate")
                e = e.replace("HONCHO_BASE_URL=http://honcho_api:8000", "HONCHO_BASE_URL=http://localhost:8006")
                e = e.replace("INTERNAL_API_URL=http://fastmcp_server:8001", "INTERNAL_API_URL=http://localhost:8001")
                e = e.replace("postgresql+psycopg://postgres:postgres@honcho_database:5432/postgres", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
                e = e.replace("redis://honcho_redis:6379/0?suppress=true", "redis://localhost:6379/0?suppress=true")
                e = e.replace("OLLAMA_BASE_URL=http://ollama_server:11434", "OLLAMA_BASE_URL=http://localhost:11434")
                new_env.append(e)
            svc["environment"] = new_env
        else:
            if "CHROMA_HOST" in env: env["CHROMA_HOST"] = "localhost"
            if "OLLAMA_HOST" in env: env["OLLAMA_HOST"] = "localhost:11434"
            if "ASSEMBLY_PC_IP" in env: env["ASSEMBLY_PC_IP"] = "localhost"
            if "PRIMARY_LLM_URL" in env: env["PRIMARY_LLM_URL"] = "http://localhost:11434/v1"
            if "OLLAMA_URL" in env: env["OLLAMA_URL"] = "http://localhost:11434/api/generate"
            if "HONCHO_BASE_URL" in env: env["HONCHO_BASE_URL"] = "http://localhost:8006"
            if "INTERNAL_API_URL" in env: env["INTERNAL_API_URL"] = "http://localhost:8001"
            if "DB_CONNECTION_URI" in env: env["DB_CONNECTION_URI"] = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
            if "CACHE_URL" in env: env["CACHE_URL"] = "redis://localhost:6379/0?suppress=true"
            if "OLLAMA_BASE_URL" in env: env["OLLAMA_BASE_URL"] = "http://localhost:11434"
            
    if svc_name == "honcho_api":
        if "environment" not in svc: svc["environment"] = []
        if isinstance(svc["environment"], list):
            svc["environment"].append("PORT=8006")
        else:
            svc["environment"]["PORT"] = "8006"
            
    if svc_name == "dozzle":
        svc["command"] = ["--addr", ":8888"]
        
    new_services[svc_name] = svc

data["services"] = new_services
if "networks" in data: del data["networks"]

out = yaml.dump(data, sort_keys=False)
with open("docker-compose.remote.yml", "w") as f:
    for h in header: f.write(h + "\n")
    f.write(out)

print("done")
