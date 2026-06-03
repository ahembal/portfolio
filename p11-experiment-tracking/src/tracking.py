"""
p11 — MLflow tracking wrapper.

Thin client used by all training scripts in the portfolio. Decouples training
code from MLflow's API surface — if the backend changes, only this file changes.

Usage:
    from src.tracking import Tracker

    tracker = Tracker(experiment="pubmed-rct")
    with tracker.run(name="lora-lr1e-4"):
        for epoch in range(num_epochs):
            tracker.log_metric("val/macro_f1", score, step=epoch)
        tracker.log_params({"lr": 1e-4, "lora_rank": 16})
        tracker.log_artifact("/tmp/model", artifact_path="model")
"""

import os
from contextlib import contextmanager
from typing import Any

import mlflow

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")


class Tracker:
    """MLflow experiment tracker."""

    def __init__(self, experiment: str) -> None:
        mlflow.set_tracking_uri(TRACKING_URI)
        mlflow.set_experiment(experiment)
        self._run = None

    @contextmanager
    def run(self, name: str | None = None, tags: dict[str, str] | None = None):
        """Context manager that wraps a single MLflow run."""
        with mlflow.start_run(run_name=name, tags=tags) as run:
            self._run = run
            yield self
        self._run = None

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        mlflow.log_metric(key, value, step=step)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        mlflow.log_metrics(metrics, step=step)

    def log_params(self, params: dict[str, Any]) -> None:
        mlflow.log_params(params)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        mlflow.log_artifact(local_path, artifact_path=artifact_path)

    @property
    def run_id(self) -> str | None:
        return self._run.info.run_id if self._run else None
