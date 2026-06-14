FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .

COPY creator_scout ./creator_scout
COPY data/seed_queries.json ./data/seed_queries.json

CMD ["python", "-m", "creator_scout.discovery.worker", "--loop", "--interval", "5", "--concurrency", "3"]
