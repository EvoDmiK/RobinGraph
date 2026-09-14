# This manifest-list digest includes linux/arm64 as well as linux/amd64.
FROM ghcr.io/astral-sh/uv:0.11.26-python3.12-trixie-slim@sha256:0130b1999b49c28d1d9a2a20793825e5ea6b808be1036e979d654196e3c7dc86

ARG VERSION=0.1.0
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="RobinGraph API" \
      org.opencontainers.image.description="Evidence-grounded bird information GraphRAG API" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="Proprietary"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN groupadd --gid 10001 robingraph \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin robingraph

WORKDIR /app

COPY --chown=robingraph:robingraph pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --python /usr/local/bin/python --locked --no-dev --no-install-project

COPY --chown=robingraph:robingraph src ./src
COPY --chown=robingraph:robingraph data/eval/v1 ./data/eval/v1
COPY --chown=robingraph:robingraph config ./config
COPY --chown=robingraph:robingraph n8n ./n8n
COPY --chown=robingraph:robingraph scripts ./scripts
RUN test -s src/robingraph/api/static/index.html \
    && test -s src/robingraph/api/static/chat.js \
    && test -s src/robingraph/api/static/styles.css
RUN uv sync --python /usr/local/bin/python --locked --no-dev

RUN install -d -o robingraph -g robingraph /app/.cache /home/robingraph/.local/state

ENV PATH="/app/.venv/bin:$PATH"

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; response = urlopen('http://127.0.0.1:8000/health', timeout=3); assert response.status == 200"]

CMD ["robingraph", "serve-fixture", "--host", "0.0.0.0", "--port", "8000"]
