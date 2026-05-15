"""
ONNX exporter for vision models (ResNet, CNN).

Uses standard torch.onnx.export with dynamic batch size.
Input shape: (batch, channels, height, width).
"""

from pathlib import Path

import torch
import torch.nn as nn


def export(model: nn.Module, input_shape: tuple, output_path: Path) -> Path:
    """
    Export a vision model to ONNX.

    Args:
        model:        PyTorch model in eval mode
        input_shape:  (channels, height, width) — batch dim added automatically
        output_path:  destination .onnx file

    Returns:
        path to the exported .onnx file
    """
    model.eval()
    dummy = torch.randn(1, *input_shape)

    torch.onnx.export(
        model,
        dummy,
        str(output_path),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        opset_version=14,
    )
    return output_path
