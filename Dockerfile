FROM python:3.11-slim@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY pyproject.toml README.md index.html ./
COPY src/ /app/src/

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --no-deps . \
    && pip uninstall -y setuptools wheel \
    && useradd --create-home --uid 10001 radar \
    && mkdir -p /app/data /app/config /app/logs \
    && chown -R radar:radar /app

USER radar
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health/ready', timeout=3)"
CMD ["radar", "serve", "--host", "0.0.0.0", "--port", "8787", "--no-demo"]
