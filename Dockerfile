FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Docker engine CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy python project manifest
COPY pyproject.toml .

# Install UV resolver for modern dependency installation
RUN pip install --no-cache-dir uv && \
    uv pip install --system . || pip install --no-cache-dir .

# Copy remaining codebase
COPY . .

# Set PYTHONPATH so the core module can be imported properly
ENV PYTHONPATH=/app/core

# Run the Swarm Mission Control API server
CMD ["python", "core/tools/infrastructure/api_server.py"]
