"""
p11 — Model promotion gate.

Compares a candidate MLflow run against the current production run and
returns a pass/fail decision. Called by CI before a new model is written
to the p8 registry.

A candidate passes if:
  - Its primary metric exceeds the production metric by at least min_delta
  - All required metrics are present in the run

Usage:
    python src/promotion.py \\
        --run-id abc123def456 \\
        --metric val/macro_f1 \\
        --min-delta 0.01 \\
        --production-tag production

Exit code 0 = promote, 1 = reject.
"""

import argparse
import os
import sys

import mlflow
from mlflow.tracking import MlflowClient

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")


def get_production_metric(client: MlflowClient, experiment_name: str, metric: str, tag: str) -> float | None:
    """Return the metric value of the current production run, or None if none exists."""
    runs = client.search_runs(
        experiment_ids=[client.get_experiment_by_name(experiment_name).experiment_id],
        filter_string=f"tags.{tag} = 'true'",
        order_by=["start_time DESC"],
        max_results=1,
    )
    if not runs:
        return None
    history = client.get_metric_history(runs[0].info.run_id, metric)
    if not history:
        return None
    return max(h.value for h in history)


def check_promotion(
    run_id: str,
    metric: str,
    min_delta: float,
    production_tag: str,
    experiment_name: str,
) -> tuple[bool, str]:
    """
    Return (passed, reason).

    passed=True  → candidate meets the bar; safe to promote.
    passed=False → candidate does not meet the bar; reason explains why.
    """
    mlflow.set_tracking_uri(TRACKING_URI)
    client = MlflowClient()

    run = client.get_run(run_id)
    candidate_history = client.get_metric_history(run_id, metric)
    if not candidate_history:
        return False, f"Metric '{metric}' not found in run {run_id}"
    candidate_value = max(h.value for h in candidate_history)

    production_value = get_production_metric(client, experiment_name, metric, production_tag)
    if production_value is None:
        return True, f"No production baseline found — first promotion passes automatically (candidate {metric}={candidate_value:.4f})"

    delta = candidate_value - production_value
    if delta >= min_delta:
        return True, f"Candidate {metric}={candidate_value:.4f} exceeds production {production_value:.4f} by {delta:+.4f} (threshold {min_delta})"
    else:
        return False, f"Candidate {metric}={candidate_value:.4f} does not exceed production {production_value:.4f} by {min_delta} (delta={delta:+.4f})"


def main() -> None:
    parser = argparse.ArgumentParser(description="MLflow model promotion gate")
    parser.add_argument("--run-id",          required=True)
    parser.add_argument("--metric",          required=True, help="MLflow metric key to compare")
    parser.add_argument("--min-delta",       type=float, default=0.01)
    parser.add_argument("--production-tag",  default="production")
    parser.add_argument("--experiment",      default="pubmed-rct")
    args = parser.parse_args()

    passed, reason = check_promotion(
        run_id=args.run_id,
        metric=args.metric,
        min_delta=args.min_delta,
        production_tag=args.production_tag,
        experiment_name=args.experiment,
    )

    print(f"{'PASS' if passed else 'FAIL'}: {reason}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
