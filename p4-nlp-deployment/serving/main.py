from logging_config import setup_logging
from middleware import RequestLoggingMiddleware

log = setup_logging()

import asyncio
import os
import time
from contextlib import asynccontextmanager

import boto3
import torch
from botocore.client import Config
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel
from starlette.responses import PlainTextResponse
from transformers import DistilBertForSequenceClassification, DistilBertTokenizerFast

# ---------------------------------------------------------------------------
# Label mapping — must match training LABEL2ID
# ---------------------------------------------------------------------------
ID2LABEL = {
    0: "BACKGROUND", 1: "OBJECTIVE", 2: "METHODS", 3: "RESULTS", 4: "CONCLUSIONS"
}
LABEL_COLOURS = {
    "BACKGROUND":  "#4A90D9",
    "OBJECTIVE":   "#E67E22",
    "METHODS":     "#27AE60",
    "RESULTS":     "#8E44AD",
    "CONCLUSIONS": "#C0392B",
}

# ---------------------------------------------------------------------------
# Prometheus metrics — try/except prevents re-registration errors in tests
# ---------------------------------------------------------------------------
try:
    REQUEST_TOTAL = Counter("nlp_requests_total", "Total predict requests", ["label"])
    REQUEST_LATENCY = Histogram(
        "nlp_request_latency_ms", "Predict latency ms",
        buckets=[10, 25, 50, 100, 200, 500, 1000],
    )
except ValueError:
    from prometheus_client import REGISTRY
    REQUEST_TOTAL = REGISTRY._names_to_collectors.get("nlp_requests_total")
    REQUEST_LATENCY = REGISTRY._names_to_collectors.get("nlp_request_latency_ms")

# ---------------------------------------------------------------------------
# Lifespan — load model from RGW once at startup
# ---------------------------------------------------------------------------
_state: dict = {}


def _load_model() -> tuple:
    rgw = os.environ["RGW_ENDPOINT"]
    bucket = os.environ.get("MODEL_BUCKET", "nlp-models")
    prefix = os.environ.get("MODEL_PREFIX", "pubmed-rct/v1")

    s3 = boto3.client(
        "s3",
        endpoint_url=rgw,
        aws_access_key_id=os.environ["RGW_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RGW_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
    )

    local_dir = "/tmp/model"
    os.makedirs(local_dir, exist_ok=True)

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            fname = os.path.basename(key)
            local_path = os.path.join(local_dir, fname)
            if not os.path.exists(local_path):
                s3.download_file(bucket, key, local_path)

    tokenizer = DistilBertTokenizerFast.from_pretrained(local_dir)
    model = DistilBertForSequenceClassification.from_pretrained(local_dir)
    model.eval()
    return tokenizer, model


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("service_starting")
    tokenizer, model = _load_model()
    _state["tokenizer"] = tokenizer
    _state["model"] = model
    _state["device"] = torch.device("cpu")
    yield
    _state.clear()


app = FastAPI(title="PubMed RCT Sentence Classifier", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    text: str


class SentenceResult(BaseModel):
    text: str
    label: str
    confidence: float
    colour: str


class PredictResponse(BaseModel):
    sentences: list[SentenceResult]
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    model: str

# ---------------------------------------------------------------------------
# Inference helper — runs in thread pool to avoid blocking event loop
# ---------------------------------------------------------------------------

def _infer(text: str) -> SentenceResult:
    tokenizer = _state["tokenizer"]
    model = _state["model"]
    device = _state["device"]

    inputs = tokenizer(
        text, return_tensors="pt", truncation=True, max_length=128, padding=True
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    label_id = int(probs.argmax())
    label = ID2LABEL[label_id]
    confidence = float(probs[label_id])

    return SentenceResult(
        text=text,
        label=label,
        confidence=round(confidence, 4),
        colour=LABEL_COLOURS[label],
    )

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    if not _state:
        raise HTTPException(status_code=503, detail="Model not loaded")

    start = time.monotonic()
    loop = asyncio.get_event_loop()

    sentences = [s.strip() for s in req.text.split(".") if s.strip()]
    if not sentences:
        raise HTTPException(status_code=422, detail="No sentences found in input")

    results = []
    for sentence in sentences:
        result = await loop.run_in_executor(None, _infer, sentence)
        REQUEST_TOTAL.labels(label=result.label).inc()
        results.append(result)

    latency_ms = (time.monotonic() - start) * 1000
    REQUEST_LATENCY.observe(latency_ms)

    return PredictResponse(sentences=results, latency_ms=round(latency_ms, 1))


@app.get("/health", response_model=HealthResponse)
async def health():
    if not _state:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return HealthResponse(status="ok", model="distilbert-pubmed-rct")


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return generate_latest()
