"""
Data preparation pipeline for p10.

Orchestrates the full Phase 1 sequence:
  1. For each WSI in wsi_dir, locate its annotation mask in mask_dir.
  2. Fit stain normaliser on reference_wsi (if method != none).
  3. Tile the WSI + mask into 512×512 patches, skip low-tissue patches.
  4. Merge scanner/site metadata (if metadata_csv provided).
  5. Assign train/val split by (scanner, site) group.
  6. Write tiles_dir/manifest.csv.

Usage:
    python data/pipeline.py --config configs/baseline.yaml

    # With scanner/site metadata (recommended):
    python data/pipeline.py --config configs/baseline.yaml \
        --metadata data/raw/metadata.csv

    # Dry-run (prints counts, writes no files):
    python data/pipeline.py --config configs/baseline.yaml --dry-run

Expected input layout:
    data/raw/wsis/   <wsi_id>.tiff  (or .svs, .ndpi — any format TIAToolbox handles)
    data/raw/masks/  <wsi_id>.png   (or .tiff — pixel values = class indices 0-3)

metadata.csv schema (optional but recommended):
    wsi_id, scanner, site
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml
from tqdm import tqdm

from data.masks import load_annotation
from data.normalise import build_normaliser
from data.split import assign_split, merge_metadata
from data.tile import tile_wsi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("p10.pipeline")

WSI_SUFFIXES = {".tiff", ".tif", ".svs", ".ndpi", ".mrxs", ".scn"}


def _find_mask(mask_dir: Path, wsi_stem: str, fmt: str) -> Path | None:
    """Locate the annotation file for a given WSI stem."""
    if fmt == "geojson":
        candidates = [mask_dir / f"{wsi_stem}.geojson", mask_dir / f"{wsi_stem}.json"]
    else:
        candidates = [
            mask_dir / f"{wsi_stem}.png",
            mask_dir / f"{wsi_stem}.tiff",
            mask_dir / f"{wsi_stem}.tif",
        ]
    for c in candidates:
        if c.exists():
            return c
    return None


def run(
    config: dict,
    metadata_csv: str | None = None,
    dry_run: bool = False,
) -> pd.DataFrame:
    data_cfg  = config["data"]
    norm_cfg  = config.get("normalisation", {})

    wsi_dir   = Path(data_cfg["wsi_dir"])
    mask_dir  = Path(data_cfg["mask_dir"])
    tiles_dir = Path(data_cfg["tiles_dir"])
    ann_fmt   = data_cfg.get("annotation_format", "mask")

    patch_size          = data_cfg["patch_size"]
    stride              = data_cfg["stride"]
    magnification       = data_cfg["magnification"]
    min_tissue_fraction = data_cfg["min_tissue_fraction"]
    val_fraction        = data_cfg["val_fraction"]
    seed                = data_cfg["seed"]

    wsi_paths = sorted(p for p in wsi_dir.iterdir() if p.suffix.lower() in WSI_SUFFIXES)

    if not wsi_paths:
        log.error("no WSI files found", extra={"dir": str(wsi_dir)})
        sys.exit(1)

    log.info("found WSIs", extra={"count": len(wsi_paths)})

    if dry_run:
        log.info("dry-run mode — no files will be written")
        for p in wsi_paths[:5]:
            mask = _find_mask(mask_dir, p.stem, ann_fmt)
            log.info("WSI", extra={"wsi": p.name, "mask": mask.name if mask else "MISSING"})
        return pd.DataFrame()

    # Fit stain normaliser once
    normaliser = build_normaliser(
        method=norm_cfg.get("method", "none"),
        reference_wsi=norm_cfg.get("reference_wsi"),
    )

    all_rows: list[dict] = []

    for wsi_path in tqdm(wsi_paths, desc="tiling WSIs"):
        mask_path = _find_mask(mask_dir, wsi_path.stem, ann_fmt)
        if mask_path is None:
            log.warning("no annotation found — skipping", extra={"wsi": wsi_path.name})
            continue

        rows = tile_wsi(
            wsi_path=wsi_path,
            mask_path=mask_path,
            tiles_dir=tiles_dir,
            patch_size=patch_size,
            stride=stride,
            magnification=magnification,
            min_tissue_fraction=min_tissue_fraction,
            normaliser=normaliser,
        )
        all_rows.extend(rows)

    manifest = pd.DataFrame(all_rows)
    manifest = merge_metadata(manifest, metadata_csv)
    manifest = assign_split(manifest, val_fraction=val_fraction, seed=seed)

    manifest_path = tiles_dir / "manifest.csv"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_path, index=False)
    log.info(
        "manifest written",
        extra={
            "path":   str(manifest_path),
            "tiles":  len(manifest),
            "train":  (manifest["split"] == "train").sum(),
            "val":    (manifest["split"] == "val").sum(),
        },
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="p10 data preparation pipeline")
    parser.add_argument("--config",   default="configs/baseline.yaml")
    parser.add_argument("--metadata", default=None,
                        help="CSV with wsi_id, scanner, site columns")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Print counts without writing any files")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    run(config, metadata_csv=args.metadata, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
