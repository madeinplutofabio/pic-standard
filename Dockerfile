FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --gid 10001 pic \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin pic

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip setuptools wheel \
    && pip install ".[langgraph,mcp,crypto]"

USER pic

EXPOSE 7580

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:7580/health')"]

ENTRYPOINT ["pic-cli", "serve"]
CMD ["--host", "0.0.0.0", "--port", "7580", "--repo-root", "/workspace"]
