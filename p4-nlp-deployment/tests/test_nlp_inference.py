"""
Tests for p4 NLP inference service.
All external calls (S3/RGW, model download) are mocked — no network required.
Model is replaced with a mock that returns fixed logits.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_state(monkeypatch):
    import torch

    from serving.main import _state

    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {
        "input_ids": torch.tensor([[1, 2, 3]]),
        "attention_mask": torch.tensor([[1, 1, 1]]),
    }

    mock_model = MagicMock()
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[0.1, 0.1, 3.0, 0.1, 0.1]])  # class 2 = METHODS
    mock_model.return_value = mock_output

    _state["tokenizer"] = mock_tokenizer
    _state["model"] = mock_model
    _state["device"] = torch.device("cpu")
    yield
    _state.clear()


@pytest.fixture
def client():
    from serving.main import app
    return TestClient(app, raise_server_exceptions=True)


class TestHealth:
    def test_returns_ok_when_model_loaded(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_returns_503_when_model_not_loaded(self):
        from serving.main import _state, app
        _state.clear()
        c = TestClient(app, raise_server_exceptions=False)
        assert c.get("/health").status_code == 503


class TestPredict:
    def test_returns_sentences_list(self, client):
        resp = client.post(
            "/predict",
            json={"text": "Patients received drug A. Results were positive."},
        )
        assert resp.status_code == 200
        assert len(resp.json()["sentences"]) == 2

    def test_each_sentence_has_required_fields(self, client):
        resp = client.post("/predict", json={"text": "Methods were applied."})
        s = resp.json()["sentences"][0]
        for field in ["text", "label", "confidence", "colour"]:
            assert field in s

    def test_label_is_valid(self, client):
        from serving.main import ID2LABEL
        resp = client.post("/predict", json={"text": "The study used a design."})
        assert resp.json()["sentences"][0]["label"] in ID2LABEL.values()

    def test_mock_returns_methods(self, client):
        resp = client.post("/predict", json={"text": "Patients were randomised."})
        assert resp.json()["sentences"][0]["label"] == "METHODS"

    def test_confidence_between_0_and_1(self, client):
        resp = client.post("/predict", json={"text": "Background information."})
        assert 0.0 <= resp.json()["sentences"][0]["confidence"] <= 1.0

    def test_returns_422_on_empty_text(self, client):
        resp = client.post("/predict", json={"text": "   "})
        assert resp.status_code == 422

    def test_latency_ms_present(self, client):
        resp = client.post("/predict", json={"text": "Methods section."})
        assert resp.json()["latency_ms"] >= 0

    def test_returns_503_when_model_not_loaded(self):
        from serving.main import _state, app
        _state.clear()
        c = TestClient(app, raise_server_exceptions=False)
        assert c.post("/predict", json={"text": "Some text."}).status_code == 503
