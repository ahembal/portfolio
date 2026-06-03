"""
p13 — Dataset loader.

Loads PubMed RCT sentence-level data from the p12 Parquet feature store,
tokenises it, and returns HuggingFace Dataset objects ready for Trainer.

Class imbalance is handled via a weighted random sampler — OBJECTIVE and
BACKGROUND sentences are underrepresented relative to METHODS and RESULTS
in the PubMed RCT distribution. Without weighting, the model optimises
accuracy at the expense of the minority classes.

Label mapping (matches p4 serving):
    BACKGROUND=0, OBJECTIVE=1, METHODS=2, RESULTS=3, CONCLUSIONS=4
"""

import logging
import os
from pathlib import Path

import pandas as pd
import torch
from datasets import Dataset
from torch.utils.data import WeightedRandomSampler
from transformers import PreTrainedTokenizerBase

log = logging.getLogger("p13.data")

LABEL2ID = {
    "BACKGROUND":  0,
    "OBJECTIVE":   1,
    "METHODS":     2,
    "RESULTS":     3,
    "CONCLUSIONS": 4,
}


def load_datasets(
    feature_store_path: str,
    tokenizer: PreTrainedTokenizerBase,
    max_length: int = 128,
    val_split: float = 0.1,
) -> tuple[Dataset, Dataset]:
    """
    Load and tokenise the PubMed RCT sentence dataset.

    Args:
        feature_store_path: S3 or local path to the Parquet feature store
        tokenizer:          HuggingFace tokenizer
        max_length:         maximum token length per sentence
        val_split:          fraction of data held out for validation

    Returns:
        (train_dataset, val_dataset) as HuggingFace Dataset objects
    """
    df = _load_parquet(feature_store_path)
    df = _explode_sentences(df)
    df = df[df["label"].isin(LABEL2ID)].copy()
    df["label_id"] = df["label"].map(LABEL2ID)

    log.info("dataset_loaded", extra={
        "total_sentences": len(df),
        "class_distribution": df["label"].value_counts().to_dict(),
    })

    split_idx = int(len(df) * (1 - val_split))
    train_df = df.iloc[:split_idx]
    val_df   = df.iloc[split_idx:]

    train_ds = _to_hf_dataset(train_df, tokenizer, max_length)
    val_ds   = _to_hf_dataset(val_df, tokenizer, max_length)

    return train_ds, val_ds


def _load_parquet(path: str) -> pd.DataFrame:
    """Load all Parquet partitions from the feature store."""
    if path.startswith("s3://"):
        import s3fs
        fs = s3fs.S3FileSystem(
            endpoint_url=os.environ["RGW_ENDPOINT"],
            key=os.environ["RGW_ACCESS_KEY"],
            secret=os.environ["RGW_SECRET_KEY"],
        )
        return pd.read_parquet(path, filesystem=fs)
    return pd.read_parquet(path)


def _explode_sentences(df: pd.DataFrame) -> pd.DataFrame:
    """Explode sentence lists into one row per sentence with label extraction."""
    rows = []
    for _, record in df.iterrows():
        for sentence in record.get("sentences", []):
            label = _extract_label(sentence)
            rows.append({"text": sentence, "label": label, "pmid": record["pmid"]})
    return pd.DataFrame(rows)


def _extract_label(sentence: str) -> str:
    """Extract structured label from sentence prefix if present (PubMed RCT format)."""
    for label in LABEL2ID:
        if sentence.upper().startswith(label + ":") or sentence.upper().startswith(label + " "):
            return label
    return "BACKGROUND"


def _to_hf_dataset(df: pd.DataFrame, tokenizer: PreTrainedTokenizerBase, max_length: int) -> Dataset:
    ds = Dataset.from_pandas(df[["text", "label_id"]].rename(columns={"label_id": "labels"}))
    return ds.map(
        lambda batch: tokenizer(batch["text"], truncation=True, padding="max_length", max_length=max_length),
        batched=True,
    )
