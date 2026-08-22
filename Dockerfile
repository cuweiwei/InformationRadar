FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY pyproject.toml README.md index.html ./
COPY src/ /app/src/

RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 radar \
    && mkdir -p /app/data /app/config /app/logs \
    && chown -R radar:radar /app

USER radar
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health/ready', timeout=3)"
CMD ["radar", "serve", "--host", "0.0.0.0", "--port", "8787", "--no-demo"]
