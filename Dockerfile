FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2-utils \
    curl \
    postgresql-client \
    libgl1 \
    libglib2.0-0 \
    libxcb1 \
    libxext6 \
    libxrender1 \
    libsm6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

RUN mkdir -p data/pdfs data/markdown data/web index logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["sh", "-c", "/app/docker-entrypoint.sh \"$@\" 2>&1 | rotatelogs -n 10 ${LOG_FILE:-/app/logs/backend.log} 5M", "--"]
