# Separate local Taste Duel image. Legacy AccessLife images/workflows are untouched.
FROM node:24.18.1-bookworm-slim@sha256:235600a8101ab264e117b1768e925532262668dc9b581ef1dd7d96ced463b8e7 AS qloo
WORKDIR /runtime/qloo
COPY runtime/qloo/package.json runtime/qloo/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY runtime/qloo/runner.mjs runtime/qloo/typed-response.mjs runtime/qloo/discovered-contract.json ./

FROM ghcr.io/astral-sh/uv:0.9.5@sha256:f459f6f73a8c4ef5d69f4e6fbbdb8af751d6fa40ec34b39a1ab469acd6e289b7 AS uv
FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
ARG SOURCE_REVISION
LABEL org.opencontainers.image.source="https://github.com/saimaharana4/taste-duel" \
    org.opencontainers.image.revision="${SOURCE_REVISION}" \
    org.opencontainers.image.title="Taste Duel API"
COPY --from=uv /uv /usr/local/bin/uv
# Node and Python stages use the same Debian generation; Node needs libstdc++.
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --no-log-init --uid 10001 tasteduel
COPY --from=qloo /usr/local/bin/node /usr/local/bin/node
WORKDIR /app/runtime/python
COPY runtime/python/pyproject.toml runtime/python/uv.lock ./
RUN uv sync --frozen --no-dev --no-cache
WORKDIR /app
COPY --from=qloo /runtime/qloo runtime/qloo
COPY apps/api/src/tasteduel apps/api/src/tasteduel
COPY apps/api/tasteduel_migrations apps/api/tasteduel_migrations
COPY apps/api/tasteduel-alembic.ini apps/api/tasteduel-alembic.ini
COPY scripts/tasteduel_qloo_offline.py scripts/tasteduel_qloo_offline.py
# Fixed one-shot maintenance/migration entry point is packaged in tasteduel.operations.
ENV PATH="/app/runtime/python/.venv/bin:$PATH" \
    PYTHONPATH=/app/apps/api/src PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    TASTEDUEL_QLOO_ENABLED=false TASTEDUEL_QLOO_RUNNER_PATH=/app/runtime/qloo/runner.mjs
USER tasteduel
EXPOSE 8000
CMD ["uvicorn", "tasteduel.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
