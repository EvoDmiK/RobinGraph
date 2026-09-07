FROM ghcr.io/astral-sh/uv:0.11.26-python3.12-trixie-slim

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
RUN uv sync --python /usr/local/bin/python --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["robingraph", "serve-fixture", "--host", "0.0.0.0", "--port", "8000"]
