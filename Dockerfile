FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create logs directory
RUN mkdir -p /app/logs

# Copy application source code
COPY . .

# Set environment variable for Python path
ENV PYTHONPATH=/app

# Default command (overridden in docker-compose.yml for api and worker)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
