FROM python:3.11-slim

WORKDIR /app

# Install system deps for playwright (optional headless browsing) and bs4
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/

# Non-root
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8001

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
