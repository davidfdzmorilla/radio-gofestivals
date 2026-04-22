FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=0

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
COPY uv.lock* ./
RUN uv sync --frozen 2>/dev/null || uv sync --no-install-project

COPY icy_worker /app/icy_worker
RUN uv sync

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["icy-worker", "serve"]
