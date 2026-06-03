"""
p13 — Evaluation metrics.

Computes per-class F1, macro F1, and accuracy. Passed to HuggingFace Trainer
as the compute_metrics callback so metrics are evaluated at every epoch and
logged to MLflow automatically.

Per-class F1 is the primary diagnostic metric. Macro F1 is the promotion gate
metric — it weights all classes equally regardless of frequency, which is
appropriate for a dataset where class imbalance is a known characteristic.
"""

import numpy as np
from sklearn.metrics import f1_score, accuracy_score, classification_report

LABEL_NAMES = ["BACKGROUND", "OBJECTIVE", "METHODS", "RESULTS", "CONCLUSIONS"]


def compute_metrics(eval_pred) -> dict:
    """
    HuggingFace Trainer-compatible metrics function.

    Returns a dict with:
        macro_f1          — macro-averaged F1 across all classes
        accuracy          — overall accuracy
        f1_{class}        — per-class F1 for each label
    """
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)

    macro_f1  = f1_score(labels, predictions, average="macro", zero_division=0)
    accuracy  = accuracy_score(labels, predictions)
    per_class = f1_score(labels, predictions, average=None, zero_division=0)

    metrics = {
        "macro_f1": round(float(macro_f1), 4),
        "accuracy": round(float(accuracy), 4),
    }
    for i, name in enumerate(LABEL_NAMES):
        metrics[f"f1_{name.lower()}"] = round(float(per_class[i]), 4)

    return metrics
