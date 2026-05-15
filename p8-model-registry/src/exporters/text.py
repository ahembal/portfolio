"""
ONNX exporter for transformer models (DistilBERT, BERT).

Uses HuggingFace optimum — direct torch.onnx.export on transformers
produces incorrect graphs due to attention masks and dynamic sequence length.
"""

from pathlib import Path


def export(model_name: str, output_dir: Path) -> Path:
    """
    Export a HuggingFace transformer model to ONNX via optimum.

    Args:
        model_name:  HuggingFace model name or local path
        output_dir:  directory where model.onnx will be written

    Returns:
        path to the exported model.onnx file
    """
    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
    except ImportError:
        raise ImportError(
            "optimum is required for transformer ONNX export. "
            "Install with: pip install optimum[onnxruntime]"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    model = ORTModelForSequenceClassification.from_pretrained(
        model_name,
        export=True,
    )
    model.save_pretrained(str(output_dir))
    return output_dir / "model.onnx"
