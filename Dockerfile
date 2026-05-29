FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
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
