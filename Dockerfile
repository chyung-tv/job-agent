# Stage 1: Build stage
FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies with uv (faster, uses lock file)
COPY pyproject.toml uv.lock* ./
RUN pip install --upgrade pip && pip install uv && uv pip install --system .

# Stage 2: Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies only (Postgres client + OpenCV runtime libs)
RUN apt-get update && apt-get install -y \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Production command (no reload)
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
