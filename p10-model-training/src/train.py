"""
Training loop for p10.

Uses HuggingFace Accelerate for fp16 mixed-precision and transparent
multi-GPU support. The same script runs on a single A100 (debug) or
four A100s (production) via `accelerate launch` without code changes.

Usage:
    # Single GPU / CPU
    python src/train.py --config configs/baseline.yaml

    # Multi-GPU on Dardel (via SLURM job)
    accelerate launch --num_processes=4 --mixed_precision=fp16 \\
        src/train.py --config configs/baseline.yaml

    # With custom data and output dirs
    python src/train.py --config configs/baseline.yaml \\
        --tiles-dir /scratch/p10/data/tiles \\
        --runs-dir  /scratch/p10/runs
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
import yaml
from accelerate import Accelerator
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from src.dataset import BeetleDataset, build_transforms
from src.evaluate import dice_score
from src.model import build_model

log = logging.getLogger("p10.train")


class DiceLoss(nn.Module):
    """Soft Dice loss — directly optimises the evaluation metric."""

    def __init__(self, num_classes: int = 4, smooth: float = 1e-6) -> None:
        super().__init__()
        self.num_classes = num_classes
        self.smooth      = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = logits.softmax(dim=1)
        loss  = 0.0
        for k in range(self.num_classes):
            p = probs[:, k]
            t = (targets == k).float()
            intersection = (p * t).sum()
            loss += 1 - (2 * intersection + self.smooth) / (p.sum() + t.sum() + self.smooth)
        return loss / self.num_classes


class CombinedLoss(nn.Module):
    """Dice + cross-entropy with configurable weights."""

    def __init__(self, num_classes: int = 4, dice_w: float = 0.5, ce_w: float = 0.5) -> None:
        super().__init__()
        self.dice = DiceLoss(num_classes)
        self.ce   = nn.CrossEntropyLoss()
        self.dice_w = dice_w
        self.ce_w   = ce_w

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.dice_w * self.dice(logits, targets) + self.ce_w * self.ce(logits, targets)


def train(
    config: dict,
    tiles_dir: str | None = None,
    runs_dir: str  | None = None,
) -> Path:
    """
    Run the full training loop.

    Returns the path to the best checkpoint directory.
    """
    data_cfg  = config["data"]
    model_cfg = config["model"]
    train_cfg = config["training"]

    tiles_dir = Path(tiles_dir or data_cfg["tiles_dir"])
    runs_dir  = Path(runs_dir  or "runs")

    run_id  = f"{model_cfg['encoder']}-{model_cfg['architecture']}-{int(time.time())}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    accelerator = Accelerator(mixed_precision=train_cfg.get("mixed_precision", "no"))

    if accelerator.is_main_process:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
        log.info("starting run", extra={"run_id": run_id})
        (run_dir / "config.yaml").write_text(yaml.dump(config))

    manifest = pd.read_csv(tiles_dir / "manifest.csv")

    train_ds = BeetleDataset(manifest, tiles_dir, split="train", transforms=build_transforms("train"))
    val_ds   = BeetleDataset(manifest, tiles_dir, split="val",   transforms=build_transforms("val"))

    train_loader = DataLoader(
        train_ds, batch_size=train_cfg["batch_size"],
        shuffle=True, num_workers=16, pin_memory=True, persistent_workers=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=train_cfg["batch_size"],
        shuffle=False, num_workers=8, pin_memory=True, persistent_workers=True,
    )

    model = build_model(model_cfg)

    optimiser = AdamW(
        model.parameters(),
        lr=train_cfg["lr"],
        weight_decay=train_cfg["weight_decay"],
    )
    scheduler = CosineAnnealingLR(optimiser, T_max=train_cfg["num_epochs"])
    criterion = CombinedLoss(
        num_classes=model_cfg["num_classes"],
        dice_w=train_cfg.get("dice_weight", 0.5),
        ce_w=train_cfg.get("ce_weight", 0.5),
    )

    model, optimiser, train_loader, val_loader, scheduler = accelerator.prepare(
        model, optimiser, train_loader, val_loader, scheduler
    )

    best_dice       = 0.0
    patience_count  = 0
    patience        = train_cfg["early_stopping_patience"]
    metrics_history = []

    for epoch in range(1, train_cfg["num_epochs"] + 1):
        model.train()
        train_loss = 0.0

        for batch in train_loader:
            images  = batch["image"].float()
            masks   = batch["mask"].long()
            logits  = model(images)

            loss = criterion(logits, masks)
            accelerator.backward(loss)
            optimiser.step()
            optimiser.zero_grad()
            train_loss += loss.item()

        train_loss /= len(train_loader)
        scheduler.step()

        # Validation
        model.eval()
        all_preds, all_targets = [], []

        with torch.no_grad():
            for batch in val_loader:
                images  = batch["image"].float()
                masks   = batch["mask"].long()
                logits  = model(images)
                preds   = logits.argmax(dim=1)

                preds, masks = accelerator.gather_for_metrics((preds, masks))
                all_preds.append(preds.cpu())
                all_targets.append(masks.cpu())

        all_preds   = torch.cat(all_preds)
        all_targets = torch.cat(all_targets)
        scores      = dice_score(all_preds, all_targets, num_classes=model_cfg["num_classes"])

        epoch_metrics = {
            "epoch":           epoch,
            "train_loss":      round(train_loss, 4),
            "dice_overall":    round(scores["overall"], 4),
            "dice_other":      round(scores.get("other", 0.0), 4),
            "dice_invasive":   round(scores.get("invasive_epithelium", 0.0), 4),
            "dice_noninvasive":round(scores.get("non_invasive_epithelium", 0.0), 4),
            "dice_necrosis":   round(scores.get("necrosis", 0.0), 4),
        }
        metrics_history.append(epoch_metrics)

        if accelerator.is_main_process:
            log.info("epoch", extra=epoch_metrics)
            (run_dir / "metrics.json").write_text(json.dumps(metrics_history, indent=2))

        if scores["overall"] > best_dice:
            best_dice      = scores["overall"]
            patience_count = 0
            accelerator.wait_for_everyone()
            if accelerator.is_main_process:
                unwrapped = accelerator.unwrap_model(model)
                torch.save(unwrapped.state_dict(), run_dir / "best.pt")
                log.info("checkpoint saved", extra={"dice": best_dice, "epoch": epoch})
        else:
            patience_count += 1
            if patience_count >= patience:
                if accelerator.is_main_process:
                    log.info("early stopping", extra={"epoch": epoch, "best_dice": best_dice})
                break

    if accelerator.is_main_process:
        log.info("training complete", extra={"run_id": run_id, "best_dice": best_dice})

    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",    default="configs/baseline.yaml")
    parser.add_argument("--tiles-dir", default=None)
    parser.add_argument("--runs-dir",  default=None)
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    train(config, tiles_dir=args.tiles_dir, runs_dir=args.runs_dir)


if __name__ == "__main__":
    main()
