with open("docker-compose.remote.yml", "r") as f:
    content = f.read()

content = content.replace("    depends_on:\n      - tailscale\n      ", "    depends_on:\n      tailscale:\n        condition: service_started\n      ")

with open("docker-compose.remote.yml", "w") as f:
    f.write(content)
