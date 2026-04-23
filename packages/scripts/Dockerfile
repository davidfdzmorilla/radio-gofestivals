# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project

COPY scripts ./scripts
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"

LABEL org.opencontainers.image.source="https://github.com/gofestivals/radio" \
      org.opencontainers.image.title="radio.gofestivals scripts" \
      org.opencontainers.image.version="0.1.0"

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 postgresql-client \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1000 radio \
 && useradd --system --uid 1000 --gid radio --no-create-home radio

WORKDIR /app

COPY --from=builder --chown=radio:radio /app/.venv /app/.venv
COPY --chown=radio:radio scripts ./scripts

USER radio

# Default command; override with `docker run <img> bootstrap-admin …` etc.
CMD ["rb_sync", "--help"]
