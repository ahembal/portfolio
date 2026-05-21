"""
Evaluation metrics for p10.

Computes per-class and overall Dice coefficient on the validation set.
Also computes per-scanner Dice when scanner metadata is available in the manifest.

Usage:
    # After training — evaluate a checkpoint
    python src/evaluate.py --config configs/baseline.yaml \\
        --checkpoint runs/<run_id>/best.pt \\
        --tiles-dir /scratch/p10/data/tiles

    # From another module
    from src.evaluate import dice_score, evaluate_checkpoint
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from torch.utils.data import DataLoader

from src.dataset import BeetleDataset, build_transforms
from src.model import build_model

log = logging.getLogger("p10.evaluate")

CLASS_NAMES = {
    0: "other",
    1: "invasive_epithelium",
    2: "non_invasive_epithelium",
    3: "necrosis",
}


def dice_score(
    preds: torch.Tensor,
    targets: torch.Tensor,
    num_classes: int = 4,
    smooth: float = 1e-6,
) -> dict[str, float]:
    """
    Compute per-class and overall Dice coefficient.

    Args:
        preds:       (N, H, W) int64 — predicted class indices
        targets:     (N, H, W) int64 — ground truth class indices
        num_classes: number of classes
        smooth:      numerical stability term

    Returns:
        dict with per-class Dice and 'overall' (mean across classes)
    """
    scores = {}
    for k in range(num_classes):
        pred_k   = (preds == k)
        target_k = (targets == k)
        intersection = (pred_k & target_k).sum().item()
        union        = pred_k.sum().item() + target_k.sum().item()
        scores[CLASS_NAMES[k]] = (2 * intersection + smooth) / (union + smooth)

    scores["overall"] = float(np.mean(list(scores.values())))
    return scores


def evaluate_checkpoint(
    config: dict,
    checkpoint: Path,
    tiles_dir: Path,
    output_path: Path | None = None,
) -> dict:
    """
    Load a checkpoint and evaluate on the val split.

    Returns a dict with per-class Dice, overall Dice, and (if scanner
    metadata is in the manifest) per-scanner Dice breakdown.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = build_model(config["model"])
    state = torch.load(checkpoint, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.to(device)
    model.eval()

    manifest = pd.read_csv(tiles_dir / "manifest.csv")
    val_ds   = BeetleDataset(manifest, tiles_dir, split="val", transforms=build_transforms("val"))
    loader   = DataLoader(val_ds, batch_size=config["training"]["batch_size"],
                          shuffle=False, num_workers=8, pin_memory=True)

    all_preds, all_targets, all_wsi_ids = [], [], []

    with torch.no_grad():
        for batch in loader:
            images  = batch["image"].float().to(device)
            masks   = batch["mask"].long()
            logits  = model(images)
            preds   = logits.argmax(dim=1).cpu()

            all_preds.append(preds)
            all_targets.append(masks)
            all_wsi_ids.extend(batch["wsi_id"])

    all_preds   = torch.cat(all_preds)
    all_targets = torch.cat(all_targets)

    overall_scores = dice_score(all_preds, all_targets, config["model"]["num_classes"])
    log.info("overall val Dice", extra=overall_scores)

    result = {"overall": overall_scores, "per_scanner": {}}

    # Per-scanner breakdown if metadata is available
    if "scanner" in manifest.columns:
        wsi_meta    = manifest.drop_duplicates("wsi_id").set_index("wsi_id")
        tile_scanners = [wsi_meta.loc[wid, "scanner"] if wid in wsi_meta.index else "unknown"
                         for wid in all_wsi_ids]
        scanners = sorted(set(tile_scanners))

        for scanner in scanners:
            mask_s  = torch.tensor([s == scanner for s in tile_scanners])
            if mask_s.sum() == 0:
                continue
            scores_s = dice_score(all_preds[mask_s], all_targets[mask_s], config["model"]["num_classes"])
            result["per_scanner"][scanner] = scores_s
            log.info("scanner Dice", extra={"scanner": scanner, **scores_s})

    if output_path is not None:
        output_path.write_text(json.dumps(result, indent=2))
        log.info("results written", extra={"path": str(output_path)})

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",     default="configs/baseline.yaml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--tiles-dir",  default=None)
    parser.add_argument("--output",     default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    with open(args.config) as f:
        config = yaml.safe_load(f)

    data_cfg  = config["data"]
    tiles_dir = Path(args.tiles_dir or data_cfg["tiles_dir"])
    output    = Path(args.output) if args.output else Path(args.checkpoint).parent / "eval.json"

    evaluate_checkpoint(config, Path(args.checkpoint), tiles_dir, output)


if __name__ == "__main__":
    main()
