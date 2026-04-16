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
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    """Return a mock nn.Module whose forward() outputs a fixed [normal] logit."""
    import torch
    mock = MagicMock()
    # logits shape (1, 2): class 0 (normal) wins
    mock.return_value = torch.tensor([[2.0, 0.5]])
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
    app_state["model"]  = mock_model
    app_state["device"] = torch.device("cpu")
    app_state["cfg"]    = MagicMock()

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
        """With logits [2.0, 0.5], softmax gives class 0 (normal)."""
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


class TestPreprocessing:
    def test_output_shape(self):
        """preprocess() should return a (1, 3, 96, 96) tensor."""
        from serving.main import preprocess
        tensor = preprocess(_make_jpeg_bytes())
        assert tensor.shape == (1, 3, 96, 96)

    def test_invalid_bytes_raises_value_error(self):
        """preprocess() should raise ValueError on non-image input."""
        from serving.main import preprocess
        with pytest.raises(ValueError):
            preprocess(b"not an image")
