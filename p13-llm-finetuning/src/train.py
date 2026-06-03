"""
p13 — LoRA fine-tuning for PubMed RCT sentence classification.

Trains a DistilBERT model with LoRA adapters on the PubMed RCT dataset.
Every run is logged to the p11 MLflow tracking server. Early stopping on
validation macro F1.

Usage:
    python src/train.py --config configs/baseline.yaml
    python src/train.py --config configs/baseline.yaml --run-name experiment-1
"""

import argparse
import logging

import yaml
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)
from peft import LoraConfig, get_peft_model, TaskType

from src.data import load_datasets
from src.evaluate import compute_metrics

log = logging.getLogger("p13.train")


def train(config: dict, run_name: str | None = None) -> str:
    """
    Run fine-tuning with the given config.

    Returns the MLflow run_id of the completed run.
    """
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent / "p11-experiment-tracking"))
    from src.tracking import Tracker

    tracker = Tracker(experiment=config.get("experiment", "pubmed-rct"))

    with tracker.run(name=run_name, tags={"model": config["model_name"]}):
        tracker.log_params({
            "model_name":      config["model_name"],
            "lora_rank":       config["lora"]["rank"],
            "lora_alpha":      config["lora"]["alpha"],
            "lora_dropout":    config["lora"]["dropout"],
            "learning_rate":   config["training"]["learning_rate"],
            "batch_size":      config["training"]["per_device_train_batch_size"],
            "num_epochs":      config["training"]["num_train_epochs"],
            "weight_decay":    config["training"]["weight_decay"],
        })

        tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
        base_model = AutoModelForSequenceClassification.from_pretrained(
            config["model_name"],
            num_labels=5,
        )

        lora_cfg = LoraConfig(
            task_type=TaskType.SEQ_CLS,
            r=config["lora"]["rank"],
            lora_alpha=config["lora"]["alpha"],
            lora_dropout=config["lora"]["dropout"],
            target_modules=["q_lin", "v_lin"],
        )
        model = get_peft_model(base_model, lora_cfg)
        log.info("lora_applied", extra={"trainable_params": sum(p.numel() for p in model.parameters() if p.requires_grad)})

        train_dataset, val_dataset = load_datasets(
            feature_store_path=config["data"]["feature_store_path"],
            tokenizer=tokenizer,
            max_length=config["data"]["max_length"],
        )

        training_args = TrainingArguments(
            output_dir=config["training"]["output_dir"],
            num_train_epochs=config["training"]["num_train_epochs"],
            per_device_train_batch_size=config["training"]["per_device_train_batch_size"],
            per_device_eval_batch_size=config["training"]["per_device_eval_batch_size"],
            learning_rate=config["training"]["learning_rate"],
            weight_decay=config["training"]["weight_decay"],
            evaluation_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="macro_f1",
            greater_is_better=True,
            report_to="mlflow",
            logging_steps=50,
            fp16=config["training"].get("fp16", False),
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            compute_metrics=compute_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
        )

        trainer.train()
        metrics = trainer.evaluate()

        tracker.log_metrics({
            "val/macro_f1":    metrics["eval_macro_f1"],
            "val/accuracy":    metrics["eval_accuracy"],
        })
        tracker.log_artifact(config["training"]["output_dir"], artifact_path="model")

        log.info("training_complete", extra={"macro_f1": metrics["eval_macro_f1"]})
        return tracker.run_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",   required=True)
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run_id = train(config, run_name=args.run_name)
    print(f"Run ID: {run_id}")


if __name__ == "__main__":
    main()
