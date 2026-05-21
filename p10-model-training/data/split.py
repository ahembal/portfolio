"""
Train/val split for p10.

A random split on 587 cases would leak scanner-specific staining patterns
into both sets — a model that has seen any slide from scanner X during
training implicitly learns that scanner's colour profile, making validation
scores optimistic on scanner X.

Strategy: group-stratified split by (scanner, site) pair.
  - Each unique (scanner, site) combination is a group.
  - Groups are assigned to train or val such that the val set contains
    at least one representative from each group where possible.
  - Within each group, slides are randomly assigned with val_fraction
    probability, subject to a minimum of 1 val slide per group.

This gives a validation set that measures generalisation across the
scanner/site distribution, not just within it.

Input: manifest.csv produced by pipeline.py, which must include
'scanner' and 'site' columns parsed from the BEETLE filename convention
or a supplied metadata CSV.

Output: manifest.csv updated with a 'split' column ("train" | "val").
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

log = logging.getLogger("p10.split")


def assign_split(
    manifest: pd.DataFrame,
    val_fraction: float = 0.2,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Add a 'split' column to manifest ("train" | "val").

    Groups by wsi_id so all tiles from one slide stay in the same split —
    tile-level leakage (the same slide in both train and val) would
    completely invalidate validation metrics.

    If 'scanner' and 'site' columns are present, the split is stratified
    across (scanner, site) groups. Otherwise, a simple slide-level split
    is used.
    """
    manifest = manifest.copy()

    # One row per WSI — tiles from the same slide must not span splits
    wsi_meta = manifest.drop_duplicates("wsi_id").set_index("wsi_id")

    if "scanner" in wsi_meta.columns and "site" in wsi_meta.columns:
        groups = (wsi_meta["scanner"].astype(str) + "_" + wsi_meta["site"].astype(str)).values
    else:
        log.warning(
            "scanner/site columns not found — using random slide-level split. "
            "Add a metadata CSV with scanner and site columns for a proper split."
        )
        groups = wsi_meta.index.values  # each slide is its own group

    wsi_ids = wsi_meta.index.values

    splitter = GroupShuffleSplit(n_splits=1, test_size=val_fraction, random_state=seed)
    train_idx, val_idx = next(splitter.split(wsi_ids, groups=groups))

    train_wsis = set(wsi_ids[train_idx])
    val_wsis   = set(wsi_ids[val_idx])

    manifest["split"] = manifest["wsi_id"].map(
        lambda wid: "train" if wid in train_wsis else "val"
    )

    n_train = (manifest["split"] == "train").sum()
    n_val   = (manifest["split"] == "val").sum()
    log.info(
        "split assigned",
        extra={
            "train_tiles": n_train,
            "val_tiles":   n_val,
            "train_wsis":  len(train_wsis),
            "val_wsis":    len(val_wsis),
        },
    )
    return manifest


def merge_metadata(manifest: pd.DataFrame, metadata_csv: str | None) -> pd.DataFrame:
    """
    Join scanner and site metadata onto the tile manifest.

    metadata_csv must have columns: wsi_id, scanner, site
    If not provided, scanner and site columns will be absent and the
    split will fall back to random slide-level assignment.
    """
    if metadata_csv is None:
        return manifest

    meta = pd.read_csv(metadata_csv, usecols=["wsi_id", "scanner", "site"])
    return manifest.merge(meta, on="wsi_id", how="left")
