"""
PyTorch Dataset for p10.

Reads tiles from the directory layout written by data/pipeline.py and
applies training-time augmentation via albumentations.

The augmentation pipeline includes stain jitter (HueSaturationValue) as a
second line of defence against scanner variation, on top of the
tile-time Macenko normalisation. This is standard practice for
multi-scanner pathology models.

Usage:
    from src.dataset import BeetleDataset, build_transforms

    train_ds = BeetleDataset(manifest, split="train", transforms=build_transforms("train"))
    val_ds   = BeetleDataset(manifest, split="val",   transforms=build_transforms("val"))

    loader = DataLoader(train_ds, batch_size=16, shuffle=True, num_workers=4)
"""

from __future__ import annotations

from pathlib import Path

import albumentations as A
import numpy as np
import pandas as pd
from albumentations.pytorch import ToTensorV2
from PIL import Image
from torch.utils.data import Dataset

NUM_CLASSES = 4


class BeetleDataset(Dataset):
    """
    Tile-level dataset for BEETLE segmentation.

    Args:
        manifest:   DataFrame from manifest.csv (must have wsi_id, filename, split columns)
        tiles_dir:  root tiles directory (contains images/ and masks/ subdirs)
        split:      "train" | "val" — filters manifest rows
        transforms: albumentations Compose pipeline; applied jointly to image + mask
    """

    def __init__(
        self,
        manifest: pd.DataFrame,
        tiles_dir: str | Path,
        split: str = "train",
        transforms: A.Compose | None = None,
    ) -> None:
        self.tiles_dir  = Path(tiles_dir)
        self.transforms = transforms
        self.rows       = manifest[manifest["split"] == split].reset_index(drop=True)

        if len(self.rows) == 0:
            raise ValueError(f"No tiles found for split={split!r} in manifest")

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> dict:
        row     = self.rows.iloc[idx]
        wsi_id  = row["wsi_id"]
        fname   = row["filename"]

        img_path  = self.tiles_dir / "images" / wsi_id / fname
        mask_path = self.tiles_dir / "masks"  / wsi_id / fname

        image = np.array(Image.open(img_path).convert("RGB"), dtype=np.uint8)
        mask  = np.array(Image.open(mask_path),               dtype=np.int64)

        if self.transforms is not None:
            out   = self.transforms(image=image, mask=mask)
            image = out["image"]
            mask  = out["mask"]

        return {"image": image, "mask": mask, "wsi_id": wsi_id, "filename": fname}


def build_transforms(split: str, patch_size: int = 512) -> A.Compose:
    """
    Build the albumentations augmentation pipeline.

    Train: geometric + colour augmentation including stain jitter.
    Val:   normalisation only (no augmentation).

    HueSaturationValue mimics stain variability and is the standard
    colour augmentation for H&E slides when Macenko normalisation alone
    is not sufficient to cover all scanner/site variation.
    """
    imagenet_mean = (0.485, 0.456, 0.406)
    imagenet_std  = (0.229, 0.224, 0.225)

    if split == "train":
        return A.Compose([
            A.RandomRotate90(p=0.5),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Transpose(p=0.5),

            # Stain jitter — simulates scanner/staining variation
            A.HueSaturationValue(
                hue_shift_limit=10,
                sat_shift_limit=20,
                val_shift_limit=10,
                p=0.7,
            ),

            A.RandomBrightnessContrast(
                brightness_limit=0.1,
                contrast_limit=0.1,
                p=0.5,
            ),

            A.GaussianBlur(blur_limit=(3, 5), p=0.2),

            A.Normalize(mean=imagenet_mean, std=imagenet_std),
            ToTensorV2(),
        ])
    else:
        return A.Compose([
            A.Normalize(mean=imagenet_mean, std=imagenet_std),
            ToTensorV2(),
        ])
