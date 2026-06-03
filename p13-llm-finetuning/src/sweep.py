"""
p13 — Hyperparameter sweep with Optuna.

Runs a Bayesian optimisation study over learning rate, LoRA rank, and batch
size. Each trial is a complete training run logged to the p11 MLflow server.
The study is seeded for reproducibility — the full search history is preserved
in MLflow and can be inspected after the fact.

Usage:
    python src/sweep.py --config configs/baseline.yaml --n-trials 20
"""

import argparse
import copy
import logging

import optuna
import yaml

from src.train import train

log = logging.getLogger("p13.sweep")


def objective(trial: optuna.Trial, base_config: dict) -> float:
    """Single Optuna trial — returns validation macro F1."""
    config = copy.deepcopy(base_config)

    config["training"]["learning_rate"] = trial.suggest_float("lr", 1e-5, 5e-4, log=True)
    config["lora"]["rank"]              = trial.suggest_categorical("lora_rank", [8, 16, 32])
    config["training"]["per_device_train_batch_size"] = trial.suggest_categorical("batch_size", [16, 32, 64])

    run_name = f"sweep-trial-{trial.number}"
    run_id = train(config, run_name=run_name)

    import mlflow
    client = mlflow.tracking.MlflowClient()
    history = client.get_metric_history(run_id, "val/macro_f1")
    return max(h.value for h in history) if history else 0.0


def run_sweep(config: dict, n_trials: int, study_name: str = "pubmed-rct-sweep") -> optuna.Study:
    study = optuna.create_study(
        study_name=study_name,
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(lambda trial: objective(trial, config), n_trials=n_trials)

    log.info("sweep_complete", extra={
        "best_value": study.best_value,
        "best_params": study.best_params,
        "n_trials": len(study.trials),
    })
    return study


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",    required=True)
    parser.add_argument("--n-trials",  type=int, default=20)
    parser.add_argument("--study",     default="pubmed-rct-sweep")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    with open(args.config) as f:
        config = yaml.safe_load(f)

    study = run_sweep(config, n_trials=args.n_trials, study_name=args.study)
    print(f"\nBest macro F1: {study.best_value:.4f}")
    print(f"Best params:   {study.best_params}")


if __name__ == "__main__":
    main()
