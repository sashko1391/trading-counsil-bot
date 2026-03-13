FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY config/ config/
COPY data/ data/

RUN mkdir -p data/logs data/trades

WORKDIR /app/src

# Railway sets PORT automatically
ENV PORT=8000
EXPOSE ${PORT}

# Real agents by default. Set BOT_ARGS="--dry-run" in Railway env vars for mocks
ENV BOT_ARGS=""
CMD sh -c "python -m api.run --port ${PORT} ${BOT_ARGS}"
