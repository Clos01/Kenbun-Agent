# --- Kenbun Mission Control Backend ---
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy the rest of the application
# Note: We will use volumes in docker-compose for live development
COPY . .

EXPOSE 8001

# Command to run the API server
CMD ["python", "tools/infrastructure/api_server.py"]
