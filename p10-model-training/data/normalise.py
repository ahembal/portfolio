"""
Stain normalisation for p10.

H&E staining varies across clinical centres and scanners. Without
normalisation, a model trained on slides from scanner A often performs
poorly on scanner B — a well-documented generalisation failure in
digital pathology.

Strategy: fit Macenko or Vahadane normalisation to a single reference
slide (specified in configs/baseline.yaml), then apply to every patch
at tile-extraction time. This ensures the tile dataset has consistent
colour statistics before training.

Alternative approach (not implemented here): apply normalisation as a
training-time augmentation (stain jitter). That approach is more
computationally expensive per epoch but avoids committing to one
reference slide. For BEETLE's multi-scanner data, tile-time normalisation
is the simpler starting point.

TIAToolbox implements both Macenko and Vahadane — consistent with p1's
use of TIAToolbox for inference.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from tiatoolbox.tools.stainextract import MacenkoStainExtractor
from tiatoolbox.tools.stainnorm import MacenkoNormaliser, VahadaneNormaliser
from tiatoolbox.wsicore.wsireader import WSIReader

log = logging.getLogger("p10.normalise")


def build_normaliser(method: str, reference_wsi: str | Path | None):
    """
    Fit and return a TIAToolbox stain normaliser.

    Args:
        method:        "macenko" | "vahadane" | "none"
        reference_wsi: path to a representative WSI used as the
                       normalisation target. Required for macenko/vahadane.

    Returns:
        A fitted normaliser with a .transform(patch_rgb) method,
        or None if method is "none".
    """
    if method == "none" or method is None:
        return None

    if reference_wsi is None:
        raise ValueError(
            f"normalisation.reference_wsi must be set in config when method={method!r}"
        )

    reference_wsi = Path(reference_wsi)
    log.info("fitting stain normaliser", extra={"method": method, "reference": str(reference_wsi)})

    # Read a representative thumbnail from the reference slide
    reader     = WSIReader.open(reference_wsi)
    target_img = reader.slide_thumbnail(resolution=20, units="power")

    if method == "macenko":
        normaliser = MacenkoNormaliser()
    elif method == "vahadane":
        normaliser = VahadaneNormaliser()
    else:
        raise ValueError(f"Unknown normalisation method: {method!r}. Use 'macenko', 'vahadane', or 'none'.")

    normaliser.fit(target_img)
    log.info("normaliser fitted")
    return normaliser


def apply(normaliser, patch_rgb: np.ndarray) -> np.ndarray:
    """
    Apply a fitted normaliser to an RGB patch (H×W×3, uint8).

    Returns the normalised patch. If the normaliser is None or the
    transform fails (e.g. near-background patch with no stain signal),
    the original patch is returned unchanged.
    """
    if normaliser is None:
        return patch_rgb
    try:
        return normaliser.transform(patch_rgb)
    except Exception as exc:
        log.debug("stain normalisation failed on patch, keeping original", extra={"error": str(exc)})
        return patch_rgb
