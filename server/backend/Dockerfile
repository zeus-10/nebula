# Docker image definition for Python FastAPI application and Celery worker

FROM python:3.10-slim

# Install system dependencies
# ffmpeg: For video processing
# libpq-dev: For Postgres connection
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Run the API Gateway with large file support
# Large file upload limits are configured in FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--limit-concurrency", "100", "--timeout-keep-alive", "5"]

