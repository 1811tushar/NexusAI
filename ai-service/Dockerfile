# NexusAI ai-service: slim, non-root, CPU-only torch, model cache on a volume, healthcheck on /health.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models SENTENCE_TRANSFORMERS_HOME=/models
WORKDIR /app

# 1) CPU-only torch FIRST (the default PyPI wheel pulls ~2 GB of CUDA libraries). sentence-transformers then sees torch as satisfied.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 10001 app && mkdir -p /models && chown -R app:app /models /app
COPY --chown=app:app app ./app
COPY --chown=app:app sql ./sql

# Optional: bake the embedding model into the image (offline start). Default off: the `models` volume caches it on first start.
ARG PRELOAD_MODEL=0
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN if [ "$PRELOAD_MODEL" = "1" ]; then python -c "from sentence_transformers import SentenceTransformer as S; S('$EMBEDDING_MODEL')"; fi \
    && chown -R app:app /models

USER app
EXPOSE 8000
# model load takes a while on first start, hence the long start-period
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
