# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Usuario no root opcional (comentado por permisos de volúmenes SMB)
# RUN useradd -ms /bin/bash app && chown -R app:app /app
# USER app

ENTRYPOINT ["icloudsync"]

