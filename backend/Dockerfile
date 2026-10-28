FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including libpq for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend, ml, data directories
COPY backend/ ./backend/
COPY ml/ ./ml/
COPY data/ ./data/

ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Backend listens internally on port 9124 per Docker routing rules
EXPOSE 9124

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:9124/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "9124", "--root-path", "/markdown-optimizer"]
