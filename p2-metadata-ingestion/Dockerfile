FROM python:3.11-slim AS builder

WORKDIR /install
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt && \
    apt-get update && apt-get install -y --no-install-recommends libmagic1 && \
    rm -rf /var/lib/apt/lists/*

FROM python:3.11-slim AS runtime

# libmagic is a C library — must be in the runtime image
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /install/bin /usr/local/bin

WORKDIR /app
COPY . .

# Non-root user
RUN adduser --disabled-password --gecos "" --uid 1001 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
