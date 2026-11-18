FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-dev.txt

# Bake the embedding model's weights into the image at build time. Without this,
# every fresh container (no persisted HF cache) downloads ~90MB from HuggingFace Hub
# on its first request/job — slow, and a runtime network dependency this app
# otherwise doesn't have. Overriding EMBEDDING_MODEL_NAME at runtime without
# rebuilding falls back to a lazy download for that model instead.
ARG EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL_NAME}')"

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
