FROM python:3.10-slim AS builder
WORKDIR /build
COPY serving/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.10-slim
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY serving/main.py .
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
ENV PYTHONPATH=/app \
    TRANSFORMERS_CACHE=/tmp/hf_cache \
    HF_HOME=/tmp/hf_home \
    TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor \
    HOME=/tmp
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
