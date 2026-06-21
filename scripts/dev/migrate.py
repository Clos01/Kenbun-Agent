import re

with open("docker-compose.remote.yml", "r") as f:
    content = f.read()

# 1. Inject tailscale
tailscale_svc = """  # 0. Tailscale Network Router
  tailscale:
    image: tailscale/tailscale:latest
    container_name: tailscale
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY?Required}
      - TS_STATE_DIR=/var/lib/tailscale
    volumes:
      - ./tailscale-state:/var/lib/tailscale
    cap_add:
      - net_admin
      - net_raw
    restart: unless-stopped

"""
content = content.replace("services:\n", "services:\n" + tailscale_svc)

# 2. Add network_mode to all
for svc in ["portable_chroma", "portable_ollama", "portable_ollama_init", "portable_fastmcp", "portable_dashboard", "portable_dozzle", "portable_honcho_api", "portable_honcho_deriver", "portable_honcho_database", "portable_honcho_redis"]:
    content = re.sub(
        f"(container_name: {svc}\\n)",
        f"\\1    network_mode: service:tailscale\\n",
        content
    )

# 3. Add tailscale dependency where depends_on already exists, or create it if missing
# Let's just create it. Wait, Ollama, chromadb don't have depends_on!
# Let's add depends_on: - tailscale to all right after network_mode
content = content.replace("    network_mode: service:tailscale\n", "    network_mode: service:tailscale\n    depends_on:\n      - tailscale\n")

# Wait, if depends_on already exists (like fastmcp_server), it will now have two depends_on blocks.
# Docker compose doesn't like duplicate keys.
# Let's fix that.
content = re.sub(r"    depends_on:\n      - tailscale\n    depends_on:\n", r"    depends_on:\n      - tailscale\n", content)

# 4. Remove ports and networks blocks
content = re.sub(r"    ports:\n(?:      - [^\n]+\n)*", "", content)
content = re.sub(r"    networks:\n(?:      - [^\n]+\n)*", "", content)

# 5. Fix internal routes
content = content.replace("CHROMA_HOST=chromadb", "CHROMA_HOST=localhost")
content = content.replace("OLLAMA_HOST=ollama_server:11434", "OLLAMA_HOST=localhost:11434")
content = content.replace("ASSEMBLY_PC_IP=ollama_server", "ASSEMBLY_PC_IP=localhost")
content = content.replace("PRIMARY_LLM_URL=http://ollama_server:11434/v1", "PRIMARY_LLM_URL=http://localhost:11434/v1")
content = content.replace("OLLAMA_URL=http://ollama_server:11434/api/generate", "OLLAMA_URL=http://localhost:11434/api/generate")
content = content.replace("HONCHO_BASE_URL=http://honcho_api:8000", "HONCHO_BASE_URL=http://localhost:8006")
content = content.replace("INTERNAL_API_URL=http://fastmcp_server:8001", "INTERNAL_API_URL=http://localhost:8001")
content = content.replace("postgresql+psycopg://postgres:postgres@honcho_database:5432/postgres", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
content = content.replace("redis://honcho_redis:6379/0?suppress=true", "redis://localhost:6379/0?suppress=true")
content = content.replace("OLLAMA_BASE_URL=http://ollama_server:11434", "OLLAMA_BASE_URL=http://localhost:11434")

# 6. Override ports
content = content.replace('image: amir20/dozzle:latest', 'image: amir20/dozzle:latest\n    command: ["--addr", ":8888"]')
content = content.replace('- OLLAMA_BASE_URL=http://localhost:11434', '- OLLAMA_BASE_URL=http://localhost:11434\n      - PORT=8006')

with open("docker-compose.remote.yml", "w") as f:
    f.write(content)
print("done")
