FROM ghcr.io/astral-sh/uv:0.9.5 AS uv
FROM python:3.12.13-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONPATH=/app/apps/api/src PYTHONUNBUFFERED=1 HF_HOME=/data/models HF_HUB_DISABLE_TELEMETRY=1 HOME=/data
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra retrieval
ARG EMBEDDING_MODEL_REVISION=c9745ed1d9f207416be6d2e6f8de32d1f16199bf
RUN HF_HOME=/opt/models .venv/bin/python -c "import os; from huggingface_hub import hf_hub_download; [hf_hub_download('sentence-transformers/all-MiniLM-L6-v2', f, revision=os.environ['EMBEDDING_MODEL_REVISION']) for f in ('tokenizer.json','onnx/model.onnx','README.md')]"
COPY third_party/MiniLM-LICENSE.txt /opt/models/MiniLM-APACHE-2.0-LICENSE
ENV HF_HOME=/opt/models HF_HUB_OFFLINE=1
COPY apps/api apps/api
COPY scripts/export_contracts.py scripts/export_contracts.py
RUN useradd --system --no-log-init --uid 10001 app && mkdir -p /data/models && chown -R app /data
USER app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "accesslife.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
