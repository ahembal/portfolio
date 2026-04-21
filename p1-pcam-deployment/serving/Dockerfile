# =============================================================================
# PCam inference service — multi-stage Docker image
#
# Stage 1 (builder): installs Python dependencies into a clean layer.
# Stage 2 (runtime): distroless base — no shell, no package manager, no OS.
#
# Why multi-stage?
# - The builder stage includes pip, wheel, and build tools that are not
#   needed at runtime. Excluding them reduces the final image size and
#   attack surface — a smaller image has fewer packages to patch.
# - Dependencies are installed before copying source code. Docker layer
#   caching means `pip install` only re-runs when requirements.txt changes,
#   not on every code change. This keeps CI builds fast.
#
# Why distroless runtime?
# - Old way: `python:3.11-slim` — a minimal Debian image. Still ships bash,
#   apt, coreutils, and ~100 other packages that the app never uses.
#   Each of those is a potential CVE surface.
# - Distroless (gcr.io/distroless/python3-debian12): contains only the Python
#   interpreter and its direct runtime dependencies. No shell, no package
#   manager, no curl, no wget. An attacker who gains code execution inside
#   the container cannot easily escalate — there are no tools to pivot with.
# - Trivy/Snyk scans show dramatically fewer CVEs vs slim.
# - Image is ~60 MB smaller than python:3.11-slim.
#
# Compliance: NIST SP 800-190 §4.1 (minimal base image), ISO 27001:2022 A.8.8
# (management of technical vulnerabilities — reduce patchable surface),
# CIS Docker Benchmark 4.1 (do not use privileged containers / minimal image).
#
# Trade-off: no shell means `kubectl exec` debugging drops to raw python -c.
# Acceptable for a production-style portfolio deployment — use an ephemeral
# debug sidecar (kubectl debug) if you need a shell in the pod.
#
# Model loading:
# The model is NOT baked into the image. It is downloaded from Ceph RGW
# at container startup via main.py's lifespan function. This means:
# - The same image works for any model version — just change MODEL_KEY
# - No need to rebuild the image when the model is retrained
# - Image stays small (~1.5 GB vs ~2.5 GB with model baked in)
#
# Required environment variables at runtime:
#   RGW_ENDPOINT     — Ceph RGW URL (default: http://192.168.1.16)
#   RGW_ACCESS_KEY   — S3 access key
#   RGW_SECRET_KEY   — S3 secret key
#   MODEL_BUCKET     — S3 bucket name (e.g. ml-artifacts)
#   MODEL_KEY        — S3 key for the model (e.g. pcam/kaggle-001/best_model.pt)
# =============================================================================

# --- Stage 1: builder --------------------------------------------------------
# Use the full slim image for building — we need pip and compilers here.
FROM python:3.11-slim AS builder

WORKDIR /build

# Copy requirements first — maximises Docker layer cache hits
COPY p1-pcam-deployment/serving/requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: runtime --------------------------------------------------------
# Distroless Python image — no shell, no package manager, no OS utilities.
# UID 65532 is the "nonroot" user that distroless ships by default.
# We do not need useradd here — the user already exists in the base image.
#
# Compliance: CIS K8s Benchmark 5.2.7 (do not admit root containers),
# NIST SP 800-190 §4.1, ISO 27001:2022 A.8.9 (configuration management —
# non-privileged runtime). Mirrored by runAsUser: 65532 in deployment.yaml.
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

# Copy installed packages from builder into the distroless image's site-packages
COPY --from=builder /install/lib/python3.11/site-packages /usr/lib/python3/dist-packages

# Copy application source
COPY p1-pcam-deployment/serving/main.py .

# Copy the shared RGW client — needed by main.py at runtime
COPY infra/ceph-rgw/boto3_config.py ./infra/ceph-rgw/boto3_config.py

EXPOSE 8080

# Distroless has no shell — CMD must use exec form (JSON array), never string form.
# String form is interpreted by /bin/sh which does not exist in this image.
# Uvicorn with a single worker — horizontal scaling is handled by K8s HPA,
# not by running multiple workers inside one pod. One process per pod keeps
# resource accounting clean and crash isolation simple.
CMD ["-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
