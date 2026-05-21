"""
Segmentation model for p10.

Architecture: encoder + U-Net or UPerNet decoder via segmentation-models-pytorch.
The encoder is swappable — ResNet-50 (ImageNet), CONCH, or Virchow2 — without
changing the decoder or training loop.

Usage:
    from src.model import build_model
    model = build_model(cfg["model"])
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

log = logging.getLogger("p10.model")

NUM_CLASSES = 4


def build_model(model_cfg: dict[str, Any]) -> nn.Module:
    """
    Build and return a segmentation model from config.

    Args:
        model_cfg: the 'model' block from baseline.yaml

    Returns:
        nn.Module with .forward(image) → logits (B, num_classes, H, W)
    """
    arch     = model_cfg["architecture"]
    encoder  = model_cfg["encoder"]
    classes  = model_cfg.get("num_classes", NUM_CLASSES)
    pretrained = model_cfg.get("pretrained", True)

    if encoder in ("resnet50", "efficientnet-b4"):
        return _build_smp(arch, encoder, classes, pretrained)
    elif encoder == "conch":
        return _build_fm_decoder(arch, "conch", classes, model_cfg)
    elif encoder == "virchow2":
        return _build_fm_decoder(arch, "virchow2", classes, model_cfg)
    else:
        raise ValueError(f"Unknown encoder: {encoder!r}. Use resnet50, efficientnet-b4, conch, or virchow2.")


def _build_smp(arch: str, encoder: str, num_classes: int, pretrained: bool) -> nn.Module:
    """Build a model using segmentation-models-pytorch."""
    import segmentation_models_pytorch as smp

    weights = "imagenet" if pretrained else None

    if arch == "unet":
        return smp.Unet(
            encoder_name=encoder,
            encoder_weights=weights,
            in_channels=3,
            classes=num_classes,
            activation=None,
        )
    elif arch == "deeplabv3plus":
        return smp.DeepLabV3Plus(
            encoder_name=encoder,
            encoder_weights=weights,
            in_channels=3,
            classes=num_classes,
            activation=None,
        )
    else:
        raise ValueError(f"Unknown architecture: {arch!r}. Use unet or deeplabv3plus.")


def _build_fm_decoder(
    arch: str,
    encoder_name: str,
    num_classes: int,
    model_cfg: dict,
) -> nn.Module:
    """
    Build an FM-encoder + lightweight decoder model.

    Foundation model encoders (CONCH, Virchow2) are loaded separately and
    wrapped in a segmentation head. The encoder is frozen or partially frozen
    depending on model_cfg['encoder_freeze'].

    Weights must be downloaded and placed at the path configured in model_cfg.
    See docs/model-options.md for access and download instructions.
    """
    encoder = _load_fm_encoder(encoder_name, model_cfg)
    decoder = _build_decoder(arch, encoder.embed_dim, num_classes)
    return FMSegmentationModel(encoder, decoder, num_classes)


def _load_fm_encoder(name: str, model_cfg: dict) -> nn.Module:
    """Load a pathology foundation model encoder."""
    weights_path = model_cfg.get(f"{name}_weights")
    if weights_path is None:
        raise ValueError(
            f"{name}_weights not set in config. "
            f"Download from HuggingFace (gated) and set the path in baseline.yaml."
        )
    weights_path = Path(weights_path)
    if not weights_path.exists():
        raise FileNotFoundError(
            f"FM encoder weights not found: {weights_path}\n"
            f"See docs/model-options.md for download instructions."
        )

    if name == "conch":
        return _load_conch(weights_path)
    elif name == "virchow2":
        return _load_virchow2(weights_path)
    else:
        raise ValueError(f"Unknown FM encoder: {name!r}")


def _load_conch(weights_path: Path) -> nn.Module:
    """
    Load CONCH ViT-B encoder.

    CONCH is a contrastive vision-language model pretrained on pathology
    image-caption pairs (MahmoodLab/CONCH on HuggingFace).
    """
    try:
        from conch.open_clip_custom import create_model_from_pretrained
        model, _ = create_model_from_pretrained("conch_ViT-B-16", str(weights_path))
        encoder = model.visual
        encoder.embed_dim = 512
        log.info("CONCH encoder loaded", extra={"path": str(weights_path)})
        return encoder
    except ImportError:
        raise ImportError(
            "CONCH requires the conch package. "
            "Install from MahmoodLab/CONCH repository after accepting the license."
        )


def _load_virchow2(weights_path: Path) -> nn.Module:
    """
    Load Virchow2 ViT-H encoder.

    Virchow2 is pretrained on 3.1M pathology slides (Paige/Virchow2 on HuggingFace).
    Won the PUMA Grand Challenge tissue segmentation task (Virchow2 + Efficient-UNet).
    """
    try:
        import timm
        model = timm.create_model(
            "hf_hub:paige-ai/Virchow2",
            pretrained=False,
            mlp_layer=timm.layers.SwiGLUPacked,
            act_layer=torch.nn.SiLU,
        )
        state = torch.load(weights_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        model.embed_dim = 1280
        log.info("Virchow2 encoder loaded", extra={"path": str(weights_path)})
        return model
    except ImportError:
        raise ImportError("Virchow2 requires timm>=0.9. pip install timm")


def _build_decoder(arch: str, embed_dim: int, num_classes: int) -> nn.Module:
    """Lightweight decoder head for FM encoders."""
    if arch == "unet":
        return SimpleUNetDecoder(embed_dim, num_classes)
    else:
        return SimpleUNetDecoder(embed_dim, num_classes)


class SimpleUNetDecoder(nn.Module):
    """
    Minimal U-Net-style decoder for FM feature maps.

    FM encoders output patch tokens (ViT). This decoder upsamples them
    progressively to the input resolution via bilinear interpolation +
    conv refinement. For production use, replace with a full UPerNet head.
    """

    def __init__(self, embed_dim: int, num_classes: int) -> None:
        super().__init__()
        self.proj   = nn.Conv2d(embed_dim, 256, 1)
        self.up1    = nn.Sequential(nn.Upsample(scale_factor=2), nn.Conv2d(256, 128, 3, padding=1), nn.ReLU())
        self.up2    = nn.Sequential(nn.Upsample(scale_factor=2), nn.Conv2d(128, 64,  3, padding=1), nn.ReLU())
        self.up3    = nn.Sequential(nn.Upsample(scale_factor=2), nn.Conv2d(64,  32,  3, padding=1), nn.ReLU())
        self.head   = nn.Conv2d(32, num_classes, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.proj(x)
        x = self.up1(x)
        x = self.up2(x)
        x = self.up3(x)
        return self.head(x)


class FMSegmentationModel(nn.Module):
    """Wraps an FM encoder + decoder into a segmentation model."""

    def __init__(self, encoder: nn.Module, decoder: nn.Module, num_classes: int) -> None:
        super().__init__()
        self.encoder    = encoder
        self.decoder    = decoder
        self.num_classes = num_classes

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, H, W = x.shape
        feats = self.encoder.forward_features(x)

        # ViT returns (B, num_tokens, embed_dim) — reshape to spatial grid
        if feats.dim() == 3:
            n_tokens = feats.shape[1]
            grid = int(n_tokens ** 0.5)
            feats = feats.reshape(B, grid, grid, -1).permute(0, 3, 1, 2)

        logits = self.decoder(feats)

        # Upsample to input resolution if needed
        if logits.shape[-2:] != (H, W):
            logits = nn.functional.interpolate(logits, size=(H, W), mode="bilinear", align_corners=False)

        return logits
