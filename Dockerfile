FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && rm -rf /var/lib/apt/lists/*

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source after deps (so code changes don't rebuild deps layer)
COPY src/ src/
COPY config/ config/
COPY data/ data/

# Create non-root user
RUN useradd --create-home appuser \
    && mkdir -p data/logs data/trades \
    && chown -R appuser:appuser /app

USER appuser

WORKDIR /app/src

# Railway sets PORT automatically
ENV PORT=8000
EXPOSE ${PORT}

# Real agents by default. Set BOT_ARGS="--dry-run" in Railway env vars for mocks
ENV BOT_ARGS=""
CMD sh -c "python -m api.run --port ${PORT} ${BOT_ARGS}"
