"""
p1-pcam-deployment/serving/main.py
------------------------------------
FastAPI inference service for the PCam binary classifier.

Loads the trained ResNet-18 model from Ceph RGW at startup via an
init function, then serves predictions via a /predict endpoint.

Design principles:

1. DEPENDENCY INJECTION
   The model and S3 client are constructed once at startup and injected
   into request handlers via FastAPI's lifespan context. Handlers never
   construct their own dependencies — this makes them testable in isolation
   by injecting mock models and clients.

2. SINGLE RESPONSIBILITY
   - load_model():   downloads and deserialises the model only
   - predict():      runs inference only
   - /health:        reports service health only
   - /predict:       accepts image bytes, returns classification only

3. FAIL FAST
   Missing environment variables and failed model downloads raise at
   startup, not at first request. A broken service never appears healthy.

4. NO LEAKY ABSTRACTION
   The endpoint accepts raw image bytes (multipart/form-data) and returns
   a plain JSON response. Callers do not need to know about PyTorch,
   ResNet, or tensor shapes — those details stay inside this module.
"""

import io
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    Counter,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

sys.path.insert(0, str(Path(__file__).resolve().parent / "infra" / "ceph-rgw"))
from boto3_config import RGWConfig, get_s3_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
# Why prometheus_client over a custom /metrics JSON endpoint?
# Prometheus has a standard text exposition format that Prometheus server
# scrapes natively. prometheus_client generates this format automatically —
# no custom serialisation, no schema design, compatible with all Prometheus
# tooling (Grafana dashboards, alerting rules, PodMonitor CRDs).
#
# Three metric types used here:
#
# Counter — monotonically increasing. Used for request counts and errors.
#   Never reset to zero (survives pod restarts gracefully in Prometheus).
#   Prometheus rate() function computes per-second rates from counters.
#
# Histogram — tracks the distribution of a value (latency here).
#   Automatically creates _count, _sum, and _bucket time series.
#   Prometheus histogram_quantile() derives p50/p95/p99 from buckets.
#   Buckets are tuned for inference latency: ResNet-18 on CPU ~10–200 ms,
#   cold start (model load) up to a few seconds — ignored by /predict buckets.
#
# Info — static key-value metadata exposed as a gauge with value=1.
#   Used here to expose model version and device — shows up in Grafana as
#   a label set, not a time series. Useful for correlating metric changes
#   with deployments.

REQUEST_COUNT = Counter(
    "pcam_requests_total",
    "Total number of requests by endpoint and HTTP status",
    ["endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "pcam_request_latency_ms",
    "Request latency in milliseconds",
    ["endpoint"],
    # Buckets tuned for CPU inference: p50 ~20 ms, p99 ~200 ms.
    # Wide upper buckets catch occasional slow requests without distorting
    # the histogram (Prometheus counts all observations above the last bucket
    # in the +Inf bucket automatically).
    buckets=[5, 10, 25, 50, 100, 200, 500, 1000, 2000],
)

MODEL_INFO = Info(
    "pcam_model",
    "Static metadata about the loaded model",
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServingConfig:
    """
    Immutable configuration for the inference service.
    All values read from environment variables at startup.
    """
    bucket:     str
    model_key:  str
    rgw_endpoint: str
    rgw_access_key: str
    rgw_secret_key: str
    model_path: str = "/tmp/best_model.pt"
    device:     str = "auto"

    @property
    def resolved_device(self) -> torch.device:
        if self.device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(self.device)

    @classmethod
    def from_env(cls) -> "ServingConfig":
        """
        Construct ServingConfig from environment variables.
        Raises immediately if required variables are missing (fail fast).
        """
        required = {
            "RGW_ACCESS_KEY": os.environ.get("RGW_ACCESS_KEY"),
            "RGW_SECRET_KEY": os.environ.get("RGW_SECRET_KEY"),
            "MODEL_BUCKET":   os.environ.get("MODEL_BUCKET"),
            "MODEL_KEY":      os.environ.get("MODEL_KEY"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {missing}"
            )
        return cls(
            bucket=required["MODEL_BUCKET"],
            model_key=required["MODEL_KEY"],
            rgw_endpoint=os.environ.get("RGW_ENDPOINT", "http://192.168.1.16"),
            rgw_access_key=required["RGW_ACCESS_KEY"],
            rgw_secret_key=required["RGW_SECRET_KEY"],
        )


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def build_model(num_classes: int = 1) -> nn.Module:
    """Build ResNet-18 with the same architecture used during training."""
    model    = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def load_model(cfg: ServingConfig) -> nn.Module:
    """
    Download model weights from Ceph RGW and load into ResNet-18.

    Downloads to cfg.model_path (default: /tmp/best_model.pt) to avoid
    writing to the container filesystem outside /tmp.

    Args:
        cfg: ServingConfig (injected)

    Returns:
        nn.Module: model in eval mode, moved to cfg.resolved_device

    Raises:
        RuntimeError: if download or weight loading fails
    """
    log.info(f"Downloading model from s3://{cfg.bucket}/{cfg.model_key}")
    rgw_cfg = RGWConfig(
        endpoint=cfg.rgw_endpoint,
        access_key=cfg.rgw_access_key,
        secret_key=cfg.rgw_secret_key,
    )
    s3 = get_s3_client(rgw_cfg)

    try:
        s3.download_file(cfg.bucket, cfg.model_key, cfg.model_path)
    except Exception as e:
        raise RuntimeError(
            f"Failed to download model from s3://{cfg.bucket}/{cfg.model_key}: {e}"
        )

    device = cfg.resolved_device
    model  = build_model()
    model.load_state_dict(
        torch.load(cfg.model_path, map_location=device)
    )
    model.to(device)
    model.eval()
    log.info(f"Model loaded on {device}")
    return model


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

TRANSFORM = transforms.Compose([
    transforms.Resize((96, 96)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

LABELS = {0: "normal", 1: "tumour"}


def preprocess(image_bytes: bytes) -> torch.Tensor:
    """
    Convert raw image bytes to a normalised tensor batch of shape (1, 3, 96, 96).

    Args:
        image_bytes: raw bytes from the uploaded file

    Returns:
        torch.Tensor: preprocessed batch ready for model inference

    Raises:
        ValueError: if the bytes cannot be decoded as an image
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Could not decode image: {e}")
    return TRANSFORM(image).unsqueeze(0)


# ---------------------------------------------------------------------------
# Application state + lifespan
# ---------------------------------------------------------------------------

# Module-level state — populated at startup, read by handlers.
# FastAPI's lifespan pattern avoids global mutation after startup.
app_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context: load model at startup, clean up at shutdown.

    Using lifespan instead of @app.on_event("startup") is the modern
    FastAPI pattern — it keeps setup and teardown co-located and avoids
    deprecated event hooks.
    """
    log.info("Service starting — loading model...")
    cfg   = ServingConfig.from_env()
    model = load_model(cfg)
    app_state["model"]  = model
    app_state["cfg"]    = cfg
    app_state["device"] = cfg.resolved_device
    # Expose static model metadata as a Prometheus Info metric.
    # This shows up in Grafana as a label set on the pcam_model_info series —
    # useful for correlating AUC/latency shifts with model version changes.
    MODEL_INFO.info({
        "model_key": cfg.model_key,
        "bucket":    cfg.bucket,
        "device":    str(cfg.resolved_device),
    })
    log.info("Model ready — service is up")
    yield
    log.info("Service shutting down")
    app_state.clear()


app = FastAPI(
    title="PCam Inference Service",
    description=(
        "Binary classifier for histopathology patches. "
        "Returns tumour/normal classification with confidence score."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """
    Liveness probe endpoint for Kubernetes.
    Returns 200 if the model is loaded and ready to serve.
    Returns 503 if the model failed to load at startup.
    """
    if "model" not in app_state:
        REQUEST_COUNT.labels(endpoint="/health", status="503").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")
    REQUEST_COUNT.labels(endpoint="/health", status="200").inc()
    return {"status": "ok", "device": str(app_state["device"])}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    """
    Classify a histopathology patch as tumour or normal.

    Accepts a JPEG or PNG image (96x96 recommended, resized automatically).
    Returns the predicted class label and confidence score.

    Args:
        file: uploaded image file (multipart/form-data)

    Returns:
        JSON with keys: label (str), confidence (float), latency_ms (float)

    Raises:
        422: if the file cannot be decoded as an image
        503: if the model is not loaded
    """
    if "model" not in app_state:
        REQUEST_COUNT.labels(endpoint="/predict", status="503").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    image_bytes = await file.read()

    try:
        tensor = preprocess(image_bytes)
    except ValueError as e:
        REQUEST_COUNT.labels(endpoint="/predict", status="422").inc()
        raise HTTPException(status_code=422, detail=str(e))

    model  = app_state["model"]
    device = app_state["device"]
    tensor = tensor.to(device)

    t0 = time.perf_counter()
    with torch.no_grad():
        logits = model(tensor)
    latency_ms = (time.perf_counter() - t0) * 1000

    # Record inference latency in the histogram. Prometheus will compute
    # p50/p95/p99 from these observations via histogram_quantile() in Grafana.
    REQUEST_LATENCY.labels(endpoint="/predict").observe(latency_ms)
    REQUEST_COUNT.labels(endpoint="/predict", status="200").inc()

    probs      = torch.softmax(logits, dim=1)[0]
    class_idx  = int(probs.argmax())
    confidence = float(probs[class_idx])

    return JSONResponse({
        "label":      LABELS[class_idx],
        "confidence": round(confidence, 4),
        "latency_ms": round(latency_ms, 2),
    })


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Exposes counters and histograms in the Prometheus text exposition format.
    Prometheus server scrapes this endpoint on a configured interval (default 15 s).

    Metrics exposed:
      pcam_requests_total{endpoint, status}   — request count by endpoint + HTTP status
      pcam_request_latency_ms{endpoint}       — inference latency histogram (ms)
      pcam_model_info{model_key, bucket, ...} — static model metadata (value=1)

    In Grafana:
      rate(pcam_requests_total[1m])                    → requests/sec
      histogram_quantile(0.95, pcam_request_latency_ms) → p95 latency
    """
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
