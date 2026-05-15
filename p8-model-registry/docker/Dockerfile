# p8 benchmark image
# Contains all ML dependencies for running PyTorch vs ONNX benchmarks.
# Code is NOT baked in — fetched from git at runtime so the image
# doesn't need to be rebuilt on every code change.
#
# Build triggers: requirements.txt changes only.

FROM python:3.12-slim

WORKDIR /bench

# Install git for runtime repo clone
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU first — separate index URL
RUN pip install --no-cache-dir torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install remaining dependencies from PyPI
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Entrypoint: clone repo, run benchmark, print results
# Arguments: <model_id> <version>
ENTRYPOINT ["/bin/sh", "-c", \
    "git clone --depth 1 https://github.com/ahembal/portfolio.git /repo && \
     cd /repo/p8-model-registry && \
     PYTHONPATH=. python src/benchmark.py \"$1\" \"$2\" && \
     cat benchmarks/\"$1\"-\"$2\"-*.yaml", \
    "--"]
