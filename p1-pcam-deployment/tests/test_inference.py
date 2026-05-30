# tests/test_inference.py
#
# Unit tests for the PCam inference service.
# These run in CI without a GPU, a real model file, or a live RGW instance.
# The model and S3 client are mocked — we're testing the FastAPI layer,
# preprocessing logic, and response contracts, not PyTorch or boto3.
#
# Run locally:
#   pytest tests/ -v

import io
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int = 96, height: int = 96) -> bytes:
    """Create a minimal JPEG image in memory — no file system needed."""
    img = Image.fromarray(
        np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_mock_model():
    """Return a mock nn.Module whose forward() outputs 2-class logits."""
    import torch
    mock = MagicMock()
    # TIAToolbox model: 2-class softmax, class 1 = tumour, class 0 = normal.
    # [2.0, -2.0] → softmax → ~[0.98, 0.02] → prob_tumour = 0.02 → label "normal".
    mock.return_value = torch.tensor([[2.0, -2.0]])
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """
    FastAPI test client with model and S3 pre-loaded into app_state.

    We bypass the lifespan function entirely — no RGW download, no GPU.
    This tests the endpoint logic in isolation.
    """
    # Patch torch.load and the S3 client so the lifespan doesn't try to
    # download anything when the app starts.
    mock_model = _make_mock_model()

    # Insert mock state directly — same keys that lifespan populates
    import torch

    from serving.main import app, app_state
    from torchvision import transforms
    app_state["model"]     = mock_model
    app_state["device"]    = torch.device("cpu")
    app_state["cfg"]       = MagicMock()
    app_state["transform"] = transforms.Compose([
        transforms.Resize((96, 96)),
        transforms.ToTensor(),
    ])

    yield TestClient(app, raise_server_exceptions=True)

    app_state.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200_when_model_loaded(self, client):
        """Health check should return 200 after model is in app_state."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_returns_503_when_model_missing(self):
        """Health check should return 503 if model never loaded (cold crash)."""
        from serving.main import app, app_state
        app_state.clear()
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/health")
        assert resp.status_code == 503


class TestPredictEndpoint:
    def test_valid_image_returns_label_and_confidence(self, client):
        """A valid JPEG should return label, confidence, and latency_ms."""
        resp = client.post(
            "/predict",
            files={"file": ("patch.jpg", _make_jpeg_bytes(), "image/jpeg")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["label"] in ("normal", "tumour")
        assert 0.0 <= body["confidence"] <= 1.0
        assert body["latency_ms"] >= 0.0

    def test_mock_model_predicts_normal(self, client):
        """Mock returns logit -2.0 → sigmoid(-2.0)=0.12 → P(tumour)<0.5 → label normal."""
        resp = client.post(
            "/predict",
            files={"file": ("patch.jpg", _make_jpeg_bytes(), "image/jpeg")},
        )
        assert resp.json()["label"] == "normal"

    def test_invalid_bytes_returns_422(self, client):
        """Non-image bytes should return 422 Unprocessable Entity."""
        resp = client.post(
            "/predict",
            files={"file": ("bad.jpg", b"this is not an image", "image/jpeg")},
        )
        assert resp.status_code == 422

    def test_predict_without_model_returns_503(self):
        """Predict should return 503 if model not loaded."""
        from serving.main import app, app_state
        app_state.clear()
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.post(
            "/predict",
            files={"file": ("patch.jpg", _make_jpeg_bytes(), "image/jpeg")},
        )
        assert resp.status_code == 503


class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client):
        """GET /metrics should return 200 with Prometheus text format."""
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")

    def test_metrics_contains_expected_counters(self, client):
        """After a predict call, /metrics must expose pcam_requests_total."""
        client.post(
            "/predict",
            files={"file": ("patch.jpg", _make_jpeg_bytes(), "image/jpeg")},
        )
        resp = client.get("/metrics")
        body = resp.text
        assert "pcam_requests_total" in body
        assert "pcam_request_latency_ms" in body

    def test_metrics_prometheus_text_format(self, client):
        """Prometheus text format lines must start with a metric name or #."""
        resp = client.get("/metrics")
        for line in resp.text.splitlines():
            if line:
                assert line.startswith("#") or line[0].isalpha(), (
                    f"Unexpected line format: {line!r}"
                )


class TestRGWIntegration:
    """
    Integration test scaffold for the S3/RGW model-loading path.

    These tests are skipped by default — they require a live Ceph RGW instance
    and the RGW_ENDPOINT / RGW_ACCESS_KEY / RGW_SECRET_KEY env vars to be set.
    Run with: pytest tests/ -m rgw

    Why skip rather than mock?
    The RGW path (boto3 → Ceph S3 API → object download) has enough real
    behaviour (presigned URLs, multipart, content-type negotiation) that mocks
    give false confidence. These tests are meant to run in staging, not in CI.
    """

    @pytest.mark.skipif(
        not all(k in __import__("os").environ for k in ("RGW_ENDPOINT", "RGW_ACCESS_KEY", "RGW_SECRET_KEY")),
        reason="RGW env vars not set — skipping RGW integration tests",
    )
    def test_load_model_from_rgw(self):
        """Model loads successfully from a real RGW bucket."""
        import os
        from serving.main import ServingConfig, load_model
        cfg = ServingConfig(
            bucket=os.environ.get("MODEL_BUCKET", "pcam-models"),
            model_key=os.environ.get("MODEL_KEY", "resnet18-pcam/best_model.pt"),
            rgw_endpoint=os.environ["RGW_ENDPOINT"],
            rgw_access_key=os.environ["RGW_ACCESS_KEY"],
            rgw_secret_key=os.environ["RGW_SECRET_KEY"],
        )
        model = load_model(cfg)
        assert model is not None


class TestPreprocessing:
    def test_output_shape(self):
        """preprocess() should return a (1, 3, 96, 96) tensor."""
        import torch
        from torchvision import transforms
        from serving.main import preprocess, app_state
        app_state["transform"] = transforms.Compose([
            transforms.Resize((96, 96)),
            transforms.ToTensor(),
        ])
        tensor = preprocess(_make_jpeg_bytes())
        assert tensor.shape == (1, 3, 96, 96)
        app_state.clear()

    def test_invalid_bytes_raises_value_error(self):
        """preprocess() should raise ValueError on non-image input."""
        from serving.main import preprocess
        with pytest.raises(ValueError):
            preprocess(b"not an image")
