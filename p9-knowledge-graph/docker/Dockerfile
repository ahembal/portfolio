# p9 graph builder image
# Clones the repo, runs builder.py, uploads graph.ttl to RGW.
# SSH deploy key and RGW credentials injected at runtime as K8s secrets.

FROM python:3.12-slim

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
