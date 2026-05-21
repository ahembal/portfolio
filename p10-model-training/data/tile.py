"""
WSI tiling for p10.

Extracts 512×512 patches at 20× magnification from each WSI, paired with
the corresponding region of the annotation mask. Patches with less than
min_tissue_fraction of foreground tissue are skipped.

Tissue detection uses Otsu thresholding on a low-resolution thumbnail —
fast and sufficient for H&E slides where background is white/near-white.

Output per WSI:
  <tiles_dir>/images/<wsi_id>/<row>_<col>.png   RGB patch
  <tiles_dir>/masks/<wsi_id>/<row>_<col>.png    4-class label mask (uint8)

The per-slide manifest rows are returned as dicts; data/pipeline.py
assembles them into the global manifest.csv.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from tiatoolbox.wsicore.wsireader import WSIReader

log = logging.getLogger("p10.tile")

# Class indices for the 4-class BEETLE task
CLASS_OTHER               = 0
CLASS_INVASIVE_EPITHELIUM = 1
CLASS_NON_INVASIVE_EPITHELIUM = 2
CLASS_NECROSIS            = 3


def _tissue_mask(reader: WSIReader, thumbnail_mpp: float = 8.0) -> np.ndarray:
    """
    Binary tissue mask at low resolution via Otsu thresholding.

    Returns a boolean array (True = tissue) at thumbnail resolution.
    thumbnail_mpp controls the resolution of the thumbnail — 8 µm/px is
    fast to compute and gives sufficient spatial accuracy for tile filtering.
    """
    thumb = reader.slide_thumbnail(resolution=thumbnail_mpp, units="mpp")
    gray  = cv2.cvtColor(np.array(thumb), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary > 0


def _tissue_fraction(
    tissue_mask: np.ndarray,
    reader: WSIReader,
    x_px: int,
    y_px: int,
    patch_size: int,
    thumbnail_mpp: float = 8.0,
) -> float:
    """
    Fraction of pixels in a patch that fall on tissue in the low-res mask.

    Converts patch coordinates from slide pixel space to thumbnail space,
    then checks the corresponding region of the tissue mask.
    """
    info = reader.info
    baseline_mpp = info.mpp  # µm per pixel at level 0

    scale = baseline_mpp / thumbnail_mpp
    tx    = int(x_px * scale)
    ty    = int(y_px * scale)
    tw    = max(1, int(patch_size * scale))
    th    = max(1, int(patch_size * scale))

    h, w = tissue_mask.shape
    tx2, ty2 = min(tx + tw, w), min(ty + th, h)
    region = tissue_mask[ty:ty2, tx:tx2]
    if region.size == 0:
        return 0.0
    return float(region.mean())


def tile_wsi(
    wsi_path: Path,
    mask_path: Path | None,
    tiles_dir: Path,
    patch_size: int = 512,
    stride: int = 512,
    magnification: float = 20.0,
    min_tissue_fraction: float = 0.5,
    normaliser=None,
) -> list[dict]:
    """
    Tile a single WSI and its annotation mask.

    Args:
        wsi_path:            path to the WSI file
        mask_path:           path to the corresponding annotation mask (None to skip mask saving)
        tiles_dir:           root output directory
        patch_size:          output patch size in pixels at target magnification
        stride:              step between patch origins (= patch_size for no overlap)
        magnification:       target objective magnification (20×)
        min_tissue_fraction: minimum tissue fraction to keep a patch
        normaliser:          optional TIAToolbox stain normaliser; applied to each RGB patch

    Returns:
        List of manifest row dicts for all saved tiles.
    """
    wsi_id = wsi_path.stem

    img_dir  = tiles_dir / "images" / wsi_id
    mask_dir = tiles_dir / "masks"  / wsi_id
    img_dir.mkdir(parents=True, exist_ok=True)
    if mask_path is not None:
        mask_dir.mkdir(parents=True, exist_ok=True)

    reader = WSIReader.open(wsi_path)
    tissue = _tissue_mask(reader)

    # Full slide dimensions at target magnification
    dims = reader.slide_dimensions(resolution=magnification, units="power")
    slide_w, slide_h = dims

    # Load annotation mask at the same resolution (if provided)
    ann_mask: np.ndarray | None = None
    if mask_path is not None:
        ann_pil   = Image.open(mask_path).convert("L")
        ann_mask  = np.array(ann_pil.resize((slide_w, slide_h), Image.NEAREST), dtype=np.uint8)

    rows = []
    n_saved = 0

    for row_idx, y in enumerate(range(0, slide_h - patch_size + 1, stride)):
        for col_idx, x in enumerate(range(0, slide_w - patch_size + 1, stride)):

            tf = _tissue_fraction(tissue, reader, x, y, patch_size)
            if tf < min_tissue_fraction:
                continue

            patch_rgb = reader.read_rect(
                location=(x, y),
                size=(patch_size, patch_size),
                resolution=magnification,
                units="power",
                coord_space="resolution",
            )

            if normaliser is not None:
                try:
                    patch_rgb = normaliser.transform(patch_rgb)
                except Exception:
                    pass  # keep unnormalised if transform fails on this patch

            fname = f"{row_idx:05d}_{col_idx:05d}.png"
            Image.fromarray(patch_rgb.astype(np.uint8)).save(img_dir / fname)

            if ann_mask is not None:
                patch_mask = ann_mask[y:y + patch_size, x:x + patch_size]
                Image.fromarray(patch_mask).save(mask_dir / fname)

            rows.append({
                "wsi_id":           wsi_id,
                "filename":         fname,
                "row":              row_idx,
                "col":              col_idx,
                "x_px":             x,
                "y_px":             y,
                "tissue_fraction":  round(tf, 4),
            })
            n_saved += 1

    log.info("tiled WSI", extra={"wsi": wsi_id, "tiles_saved": n_saved})
    return rows
