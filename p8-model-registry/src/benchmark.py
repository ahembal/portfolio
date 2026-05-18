"""
Benchmark framework — compare PyTorch vs ONNX Runtime for a registered model.

Answers two questions before switching a serving container:
  1. Do outputs agree within tolerance? (correctness gate)
  2. How much faster is ONNX on this hardware? (justification for switching)

Usage:
  python src/benchmark.py resnet18-tiatoolbox-pcam v1
  python src/benchmark.py distilbert-pubmed-rct v1
"""

import datetime
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import psutil
import yaml

REGISTRY  = Path(__file__).parent.parent / "registry"
BENCHMARKS = Path(__file__).parent.parent / "benchmarks"
WARMUP_RUNS = 10
BENCH_RUNS  = 100
OUTPUT_TOLERANCE = 1e-4


def _percentiles(latencies: list[float]) -> dict[str, float]:
    a = np.array(latencies)
    return {
        "p50_ms": round(float(np.percentile(a, 50)), 2),
        "p95_ms": round(float(np.percentile(a, 95)), 2),
        "p99_ms": round(float(np.percentile(a, 99)), 2),
    }


def _memory_mb(fn, *args) -> tuple[Any, float]:
    """Run fn(*args), return (result, peak_memory_mb)."""
    proc = psutil.Process()
    before = proc.memory_info().rss
    result = fn(*args)
    after = proc.memory_info().rss
    return result, round((after - before) / 1024 / 1024, 2)


def _run_pytorch(model, inputs: np.ndarray, n: int) -> tuple[np.ndarray, list[float]]:
    """Run n inferences with PyTorch, return (output, latencies_ms)."""
    import torch
    tensor = torch.tensor(inputs)
    latencies = []
    output = None
    for i in range(n + WARMUP_RUNS):
        t0 = time.perf_counter()
        with torch.no_grad():
            out = model(tensor)
        latencies.append((time.perf_counter() - t0) * 1000)
        if i == WARMUP_RUNS - 1:
            output = out.numpy()
    return output, latencies[WARMUP_RUNS:]


def _run_onnx(session, inputs: np.ndarray, input_name: str, n: int) -> tuple[np.ndarray, list[float]]:
    """Run n inferences with ONNX Runtime, return (output, latencies_ms)."""
    latencies = []
    output = None
    for i in range(n + WARMUP_RUNS):
        t0 = time.perf_counter()
        out = session.run(None, {input_name: inputs})
        latencies.append((time.perf_counter() - t0) * 1000)
        if i == WARMUP_RUNS - 1:
            output = out[0]
    return output, latencies[WARMUP_RUNS:]


def _check_agreement(pt_out: np.ndarray, onnx_out: np.ndarray) -> dict:
    diff = float(np.max(np.abs(pt_out - onnx_out)))
    return {
        "max_abs_diff": round(diff, 8),
        "tolerance": OUTPUT_TOLERANCE,
        "passed": diff < OUTPUT_TOLERANCE,
    }


def _verdict(agreement: dict, speedup_p50: float, speedup_p95: float, speedup_p99: float) -> str:
    if not agreement["passed"]:
        return "✗ Export broken — outputs disagree, do not use ONNX"
    mean_speedup = round((speedup_p50 + speedup_p95 + speedup_p99) / 3, 2)
    summary = f"p50={speedup_p50:.2f}x p95={speedup_p95:.2f}x p99={speedup_p99:.2f}x mean={mean_speedup:.2f}x"
    if mean_speedup < 1.5:
        return f"— Marginal gain ({summary}), review before switching"
    return f"✓ ONNX recommended — outputs agree, {summary}"


def _download_from_rgw(location: str, dest: Path) -> Path:
    """Download a file from RGW. Credentials read from env: RGW_ENDPOINT, RGW_ACCESS_KEY, RGW_SECRET_KEY."""
    import boto3

    parsed = urlparse(location)
    bucket = parsed.netloc
    key    = parsed.path.lstrip("/")

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["RGW_ENDPOINT"],
        aws_access_key_id=os.environ["RGW_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RGW_SECRET_KEY"],
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, key, str(dest))
    return dest


def _build_model_dir(entry: dict, tmp_dir: Path) -> Path:
    """
    Reconstruct a local HuggingFace model directory from a registry entry.

    transformers.AutoModelForSequenceClassification.from_pretrained() requires
    a directory containing three things: config.json (architecture + output
    shape + class names), tokenizer files, and model weights. RGW only stores
    the weights (model.safetensors) — the config and tokenizer are not saved
    there because they are identical to the base model except for num_labels
    and the class mapping.

    This function assembles that directory in a temp location:
      1. Downloads config.json from the base model on HuggingFace Hub
      2. Patches num_labels and id2label/label2id to match the fine-tuned head
      3. Copies tokenizer files from the base model (unchanged by fine-tuning)
      4. Downloads fine-tuned weights from RGW
    """
    import shutil
    from huggingface_hub import hf_hub_download

    arch = entry["architecture"]  # e.g. "distilbert-base-uncased"
    id2label = {
        str(k): v
        for k, v in entry["class_mapping"].items()
        if isinstance(k, int)
    }
    label2id = {v: str(k) for k, v in id2label.items()}

    model_dir = tmp_dir / "model"
    model_dir.mkdir()
    base_cache = tmp_dir / "base"

    # Patch base config for fine-tuned classification head
    config_src = hf_hub_download(arch, "config.json", local_dir=str(base_cache))
    with open(config_src) as f:
        config = json.load(f)
    config.update({
        "architectures": [f"{arch.split('-')[0].capitalize()}ForSequenceClassification"],
        "num_labels": len(id2label),
        "id2label": id2label,
        "label2id": label2id,
    })
    with open(model_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Copy tokenizer files from base model
    for fname in ["tokenizer.json", "tokenizer_config.json", "vocab.txt", "special_tokens_map.json"]:
        try:
            src = hf_hub_download(arch, fname, local_dir=str(base_cache))
            shutil.copy(src, model_dir / fname)
        except Exception:
            pass

    # Fine-tuned weights from RGW
    _download_from_rgw(entry["origin"]["location"], model_dir / "model.safetensors")
    return model_dir


def benchmark_text(model_id: str, version: str, entry: dict) -> dict:
    """Benchmark a text classification model (DistilBERT etc.)."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from optimum.onnxruntime import ORTModelForSequenceClassification

    # Representative sample across the 5 PubMed RCT classes
    sample_texts = [
        "Randomized controlled trials have shown that statins reduce cardiovascular events.",
        "This study aimed to evaluate the efficacy of metformin in type 2 diabetes.",
        "Patients were randomized 1:1 to receive either treatment A or placebo.",
        "The primary endpoint was all-cause mortality at 12 months.",
        "In conclusion, the intervention significantly reduced HbA1c levels.",
    ]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print("  Downloading model from RGW and building model directory...")
        model_dir = _build_model_dir(entry, tmp_path)

        tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        pt_tokens = tokenizer(
            sample_texts, return_tensors="pt",
            padding=True, truncation=True, max_length=512,
        )

        # --- PyTorch ---
        proc = psutil.Process()
        before = proc.memory_info().rss
        pt_model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        pt_model.eval()
        pt_mem = round((proc.memory_info().rss - before) / 1024 / 1024, 2)

        pt_latencies = []
        pt_output = None
        for i in range(BENCH_RUNS + WARMUP_RUNS):
            t0 = time.perf_counter()
            with torch.no_grad():
                out = pt_model(**pt_tokens)
            pt_latencies.append((time.perf_counter() - t0) * 1000)
            if i == WARMUP_RUNS - 1:
                pt_output = out.logits.numpy()
        pt_latencies = pt_latencies[WARMUP_RUNS:]

        # --- ONNX via optimum ---
        before = proc.memory_info().rss
        ort_model = ORTModelForSequenceClassification.from_pretrained(str(model_dir), export=True)
        onnx_mem = round((proc.memory_info().rss - before) / 1024 / 1024, 2)

        ort_tokens = tokenizer(
            sample_texts, return_tensors="pt",
            padding=True, truncation=True, max_length=512,
        )
        onnx_latencies = []
        onnx_output = None
        for i in range(BENCH_RUNS + WARMUP_RUNS):
            t0 = time.perf_counter()
            out = ort_model(**ort_tokens)
            onnx_latencies.append((time.perf_counter() - t0) * 1000)
            if i == WARMUP_RUNS - 1:
                onnx_output = out.logits.numpy()
        onnx_latencies = onnx_latencies[WARMUP_RUNS:]

    pt_p   = _percentiles(pt_latencies)
    onnx_p = _percentiles(onnx_latencies)
    agreement = _check_agreement(pt_output, onnx_output)
    speedup_p50 = round(pt_p["p50_ms"] / onnx_p["p50_ms"], 2)
    speedup_p95 = round(pt_p["p95_ms"] / onnx_p["p95_ms"], 2)
    speedup_p99 = round(pt_p["p99_ms"] / onnx_p["p99_ms"], 2)

    return {
        "pytorch": {**pt_p, "memory_mb": pt_mem},
        "onnx":    {**onnx_p, "memory_mb": onnx_mem},
        "output_agreement": agreement,
        "speedup": {
            "p50": f"{speedup_p50}x",
            "p95": f"{speedup_p95}x",
            "p99": f"{speedup_p99}x",
        },
        "verdict": _verdict(agreement, speedup_p50, speedup_p95, speedup_p99),
    }


def benchmark_vision(model_id: str, version: str, entry: dict) -> dict:
    """Benchmark a vision model (ResNet-18 etc.)."""
    import timm
    import torch
    import onnxruntime as ort
    from src.exporters.vision import export as export_onnx

    input_shape = entry["preprocessing"]["input_size"]  # [C, H, W]
    np.random.seed(42)
    inputs = np.random.randn(1, *input_shape).astype(np.float32)

    # Load PyTorch model
    hub_id = entry["origin"]["hub_id"]
    pt_model = timm.create_model(f"hf-hub:{hub_id}", pretrained=True).eval()

    # Measure PyTorch
    pt_out, pt_mem = _memory_mb(_run_pytorch, pt_model, inputs, BENCH_RUNS)
    pt_latencies = pt_out[1]
    pt_output    = pt_out[0]

    # Export and load ONNX
    with tempfile.TemporaryDirectory() as tmp:
        onnx_path = Path(tmp) / "model.onnx"
        export_onnx(pt_model, input_shape, onnx_path)
        session = ort.InferenceSession(str(onnx_path))
        input_name = session.get_inputs()[0].name

        onnx_result, onnx_mem = _memory_mb(_run_onnx, session, inputs, input_name, BENCH_RUNS)
        onnx_latencies = onnx_result[1]
        onnx_output    = onnx_result[0]

    pt_p   = _percentiles(pt_latencies)
    onnx_p = _percentiles(onnx_latencies)
    agreement = _check_agreement(pt_output, onnx_output)
    speedup_p50 = round(pt_p["p50_ms"] / onnx_p["p50_ms"], 2)
    speedup_p95 = round(pt_p["p95_ms"] / onnx_p["p95_ms"], 2)
    speedup_p99 = round(pt_p["p99_ms"] / onnx_p["p99_ms"], 2)

    return {
        "pytorch": {**pt_p,   "memory_mb": pt_mem},
        "onnx":    {**onnx_p, "memory_mb": onnx_mem},
        "output_agreement": agreement,
        "speedup": {
            "p50": f"{speedup_p50}x",
            "p95": f"{speedup_p95}x",
            "p99": f"{speedup_p99}x",
        },
        "verdict": _verdict(agreement, speedup_p50, speedup_p95, speedup_p99),
    }


def benchmark(model_id: str, version: str) -> dict:
    """
    Run the full benchmark for a registered model.

    Args:
        model_id: model id from registry
        version:  version string e.g. "v1"

    Returns:
        result dict written to benchmarks/
    """
    yaml_path = REGISTRY / "models" / f"{model_id}-{version}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"{yaml_path} not found in registry")

    with open(yaml_path) as f:
        entry = yaml.safe_load(f)

    print(f"Benchmarking {model_id} {version}...")
    print(f"  Task: {entry['task']}, Architecture: {entry['architecture']}")
    print(f"  Runs: {BENCH_RUNS} (+ {WARMUP_RUNS} warmup)")

    task = entry["task"]
    arch = entry["architecture"]
    if task == "binary-classification" and arch.startswith("resnet"):
        results = benchmark_vision(model_id, version, entry)
    elif task == "multiclass-classification" and arch.startswith("distilbert"):
        results = benchmark_text(model_id, version, entry)
    else:
        raise NotImplementedError(
            f"Benchmark not implemented for task={task}, arch={arch}. "
            f"Add an exporter in src/exporters/ and a benchmark case in src/benchmark.py."
        )

    result = {
        "id": f"{model_id}-{version}-{datetime.date.today()}",
        "model_id": model_id,
        "model_version": version,
        "date": str(datetime.date.today()),
        "hardware": platform.node(),
        "n_runs": BENCH_RUNS,
        "warmup_runs": WARMUP_RUNS,
        **results,
    }

    BENCHMARKS.mkdir(exist_ok=True)
    out_path = BENCHMARKS / f"{result['id']}.yaml"
    with open(out_path, "w") as f:
        yaml.dump(result, f, default_flow_style=False, sort_keys=False)

    print(f"\nResult saved to {out_path}")
    print(f"Verdict: {result['verdict']}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: benchmark.py <model_id> <version>")
        sys.exit(1)
    benchmark(sys.argv[1], sys.argv[2])
