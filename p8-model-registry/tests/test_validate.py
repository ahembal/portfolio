"""
Tests for src/validate.py — registry entry validation and cross-reference checks.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.validate import validate_entry, validate_cross_references, validate_all


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry_dir(tmp_path):
    """Minimal registry with one valid entry per type."""
    for subdir in ("models", "experiments", "evaluations", "deployments"):
        (tmp_path / subdir).mkdir()

    (tmp_path / "models" / "model-v1.yaml").write_text(yaml.dump({
        "id": "test-model",
        "version": "v1",
        "created_at": "2026-01-01",
        "task": "binary-classification",
        "architecture": "resnet18",
        "source": "pretrained",
        "format": "safetensors",
        "sha": "abc123" * 10,
        "origin": {"type": "huggingface", "hub_id": "org/model"},
        "preprocessing": {"input_size": [3, 96, 96]},
        "class_mapping": {0: "normal", 1: "tumour"},
    }))

    (tmp_path / "experiments" / "exp-001.yaml").write_text(yaml.dump({
        "id": "exp-001",
        "date": "2026-01-01",
        "model_id": "test-model",
        "framework": "pytorch",
        "compute": {"type": "gpu"},
        "hyperparameters": {"lr": 0.001},
        "artifact": {"sha": "def456" * 10, "path": "s3://bucket/model.pt"},
    }))

    (tmp_path / "evaluations" / "eval-001.yaml").write_text(yaml.dump({
        "id": "eval-001",
        "date": "2026-01-02",
        "model_id": "test-model",
        "model_version": "v1",
        "evaluator": "pytest",
        "dataset": {"name": "pcam-test"},
        "threshold": 0.5,
        "metrics": {"auc": 0.96},
    }))

    (tmp_path / "deployments" / "dep-001.yaml").write_text(yaml.dump({
        "id": "dep-001",
        "model_id": "test-model",
        "model_version": "v1",
        "evaluation_id": "eval-001",
        "environment": "prod",
        "deployed_at": "2026-01-03",
        "deployed_by": "ci",
        "status": "active",
        "service": "pcam-inference",
    }))

    return tmp_path


# ---------------------------------------------------------------------------
# validate_entry
# ---------------------------------------------------------------------------

class TestValidateEntry:
    def test_valid_model_returns_no_errors(self, registry_dir):
        path = registry_dir / "models" / "model-v1.yaml"
        errors = validate_entry(path, "models")
        assert errors == []

    def test_missing_required_field_returns_error(self, tmp_path):
        (tmp_path / "models").mkdir()
        bad = tmp_path / "models" / "bad.yaml"
        bad.write_text(yaml.dump({"id": "x", "version": "v1"}))
        errors = validate_entry(bad, "models")
        assert any("sha" in e for e in errors)

    def test_unverified_sha_returns_trust_error(self, tmp_path):
        (tmp_path / "models").mkdir()
        entry = tmp_path / "models" / "unverified.yaml"
        data = {
            "id": "x", "version": "v1", "created_at": "2026-01-01",
            "task": "t", "architecture": "a", "source": "s", "format": "f",
            "sha": "UNVERIFIED",
            "origin": {}, "preprocessing": {}, "class_mapping": {},
        }
        entry.write_text(yaml.dump(data))
        errors = validate_entry(entry, "models")
        assert any("UNVERIFIED" in e or "trust" in e.lower() for e in errors)

    def test_empty_file_returns_error(self, tmp_path):
        (tmp_path / "models").mkdir()
        empty = tmp_path / "models" / "empty.yaml"
        empty.write_text("")
        errors = validate_entry(empty, "models")
        assert errors


# ---------------------------------------------------------------------------
# validate_cross_references
# ---------------------------------------------------------------------------

class TestValidateCrossReferences:
    def test_valid_registry_passes(self, registry_dir, monkeypatch):
        import src.validate as v
        monkeypatch.setattr(v, "REGISTRY", registry_dir)
        errors = validate_cross_references()
        assert errors == []

    def test_deployment_with_unknown_evaluation_fails(self, registry_dir, monkeypatch):
        import src.validate as v
        monkeypatch.setattr(v, "REGISTRY", registry_dir)

        dep_file = registry_dir / "deployments" / "dep-001.yaml"
        data = yaml.safe_load(dep_file.read_text())
        data["evaluation_id"] = "nonexistent-eval"
        dep_file.write_text(yaml.dump(data))

        errors = validate_cross_references()
        assert any("nonexistent-eval" in e for e in errors)

    def test_evaluation_with_unknown_model_fails(self, registry_dir, monkeypatch):
        import src.validate as v
        monkeypatch.setattr(v, "REGISTRY", registry_dir)

        eval_file = registry_dir / "evaluations" / "eval-001.yaml"
        data = yaml.safe_load(eval_file.read_text())
        data["model_id"] = "ghost-model"
        eval_file.write_text(yaml.dump(data))

        errors = validate_cross_references()
        assert any("ghost-model" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_all against real registry
# ---------------------------------------------------------------------------

class TestValidateAllRealRegistry:
    def test_real_registry_passes_validation(self):
        """The committed registry entries must pass validate_all without errors."""
        ok = validate_all()
        assert ok, "Registry validation failed — run python src/validate.py for details"
