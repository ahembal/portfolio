# p8 benchmark image
# Clones the repo, runs benchmark, commits results back via SSH deploy key.
# Deploy key is injected at runtime as a Kubernetes secret — not baked in.

FROM python:3.12-slim

WORKDIR /bench

RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU first — separate index URL
RUN pip install --no-cache-dir torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install remaining dependencies from PyPI
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Entrypoint:
#   1. Configure SSH using deploy key mounted at /secrets/ssh-key
#   2. Clone repo
#   3. Run benchmark
#   4. Commit and push results
# Arguments: <model_id> <version>
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
