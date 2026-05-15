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
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

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
    if task == "binary-classification" and entry["architecture"].startswith("resnet"):
        results = benchmark_vision(model_id, version, entry)
    else:
        raise NotImplementedError(
            f"Benchmark not implemented for task={task}, arch={entry['architecture']}. "
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
