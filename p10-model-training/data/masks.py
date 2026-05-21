"""
Annotation mask handling for p10.

BEETLE provides pixel-level annotations. Two formats are supported:

  "mask"    — a TIFF/PNG image the same size as the WSI where each pixel
              value is a class index (0–3). This is the format used for
              BEETLE mask-based annotations downloaded from Grand Challenge.

  "geojson" — polygon annotations with a class property. Each polygon
              covers a region of the slide; pixels inside are assigned the
              polygon's class. Used by some GC challenges instead of rasters.

The output in both cases is a uint8 PNG mask at the dimensions passed in,
ready to be sliced by tile.py.

Class mapping (BEETLE):
  0  other                   stroma, fat, background, normal tissue
  1  invasive_epithelium
  2  non_invasive_epithelium
  3  necrosis
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

log = logging.getLogger("p10.masks")

CLASS_MAP = {
    "other":                    0,
    "invasive_epithelium":      1,
    "invasive epithelium":      1,
    "non_invasive_epithelium":  2,
    "non-invasive epithelium":  2,
    "non_invasive epithelium":  2,
    "necrosis":                 3,
}


def load_mask_tiff(mask_path: Path) -> np.ndarray:
    """
    Load a TIFF/PNG mask where pixel value = class index.

    Validates that all values are in [0, 3]. Any value > 3 is remapped
    to 0 (other) with a warning — handles palette images that encode
    class as RGB triplets by converting to grayscale first.
    """
    img = Image.open(mask_path)

    if img.mode == "RGB":
        arr = np.array(img)
        # Some GC challenges encode class as a palette colour; take red channel
        # as the class index assuming a simple 1-channel-encoded palette.
        arr = arr[:, :, 0]
        log.warning("RGB mask detected — using red channel as class index", extra={"path": str(mask_path)})
    elif img.mode == "P":
        arr = np.array(img.convert("L"))
    else:
        arr = np.array(img)

    arr = arr.astype(np.uint8)
    out_of_range = (arr > 3).sum()
    if out_of_range > 0:
        log.warning(
            "mask has pixels with class > 3, remapping to 0",
            extra={"path": str(mask_path), "count": int(out_of_range)},
        )
        arr[arr > 3] = 0

    return arr


def load_mask_geojson(geojson_path: Path, slide_w: int, slide_h: int) -> np.ndarray:
    """
    Rasterise a GeoJSON polygon annotation into a class mask.

    Each feature must have a 'classification' property with a 'name' key
    that maps to CLASS_MAP. Features are drawn in CLASS_MAP order so that
    higher-priority classes (necrosis > invasive > non-invasive) overwrite
    lower-priority background regions.

    GeoJSON coordinates are assumed to be in slide pixel space (x, y at
    the magnification level at which the annotations were made — typically
    the base resolution of the WSI).
    """
    mask = np.zeros((slide_h, slide_w), dtype=np.uint8)

    with open(geojson_path) as f:
        gj = json.load(f)

    features = gj.get("features", [])

    # Draw in ascending class index order so higher classes paint over lower
    priority = sorted(features, key=lambda feat: _class_index(feat))

    for feat in priority:
        cls = _class_index(feat)
        geom = feat.get("geometry", {})
        if geom.get("type") == "Polygon":
            _draw_polygon(mask, geom["coordinates"][0], cls)
        elif geom.get("type") == "MultiPolygon":
            for ring_group in geom["coordinates"]:
                _draw_polygon(mask, ring_group[0], cls)

    return mask


def _class_index(feature: dict) -> int:
    props = feature.get("properties", {})
    name  = (
        props.get("classification", {}).get("name", "other")
        if isinstance(props.get("classification"), dict)
        else props.get("class", "other")
    )
    return CLASS_MAP.get(name.lower().strip(), 0)


def _draw_polygon(mask: np.ndarray, coords: list, class_idx: int) -> None:
    pts = np.array([[int(x), int(y)] for x, y in coords], dtype=np.int32)
    cv2.fillPoly(mask, [pts], color=class_idx)


def load_annotation(
    ann_path: Path,
    fmt: str = "mask",
    slide_w: int | None = None,
    slide_h: int | None = None,
) -> np.ndarray:
    """
    Unified annotation loader.

    Args:
        ann_path:  path to the annotation file
        fmt:       "mask" or "geojson"
        slide_w:   required for geojson — target mask width in pixels
        slide_h:   required for geojson — target mask height in pixels
    """
    if fmt == "mask":
        return load_mask_tiff(ann_path)
    elif fmt == "geojson":
        if slide_w is None or slide_h is None:
            raise ValueError("slide_w and slide_h are required for geojson format")
        return load_mask_geojson(ann_path, slide_w, slide_h)
    else:
        raise ValueError(f"Unknown annotation format: {fmt!r}. Use 'mask' or 'geojson'.")
