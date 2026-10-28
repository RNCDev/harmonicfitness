# The web client's image. Railway builds it from the GitHub repo and runs it as two services,
# WT_ROLE=web and WT_ROLE=worker (web/entrypoint.sh). The local voice engine is not installed:
# only the `web` extra, so a job's engine runs the lint, brief and web voices, never PyTorch.

FROM node:20-slim AS client
WORKDIR /src/web/client
COPY web/client/package.json web/client/package-lock.json ./
RUN npm ci
COPY web/client/ ./
RUN npm run build

FROM python:3.11-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tini \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

# The repo is /app and its environment /app/.venv, where ./sweatcast looks (tools/common.sh).
# SWEATCAST_PYTHON makes that explicit, so the wrapper never runs uv or reaches the network at job time.
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON_PREFERENCE=only-system \
    SWEATCAST_PYTHON=/app/.venv/bin/python \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --extra web --no-dev

COPY . .
COPY --from=client /src/web/client/dist web/client/dist

RUN python -m compileall -q /app/tools /app/web/webapp

RUN useradd --system --uid 10001 --create-home app
USER app
EXPOSE 8000
# tini is PID 1, so an engine grandchild orphaned by a killed job is reaped, not left a zombie
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "/app/web/entrypoint.sh"]
