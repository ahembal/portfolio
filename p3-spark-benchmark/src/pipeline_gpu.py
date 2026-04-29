"""
GPU pipeline using cuDF (RAPIDS) — runs on Dardel AMD MI250X via ROCm.

cuDF mirrors the pandas API so the logic is identical to pipeline_pandas.py.
Key differences:
  - Data lives in GPU HBM — no RAM pressure for 10M/40M row datasets
  - Rolling window: cuDF supports cumsum over groupby natively
  - ROCm backend on Dardel (MI250X) instead of CUDA (A100)

Usage:
    python src/pipeline_gpu.py --data data/sra_runs_10M.parquet --out results/

On Dardel:
    sbatch jobs/dardel_gpu.sh
"""

import argparse
import json
import time
from pathlib import Path

try:
    import cudf
    import cudf.pandas  # noqa: F401 — enables cudf.pandas acceleration
    GPU_AVAILABLE = True
except ImportError:
    import pandas as cudf   # fallback for local testing without GPU
    GPU_AVAILABLE = False
    print("WARNING: cuDF not available — falling back to pandas (for testing only)")


def run_pipeline(data_path: str, lookup_path: str, out_dir: str) -> dict:
    scale = Path(data_path).stem
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    timings = {}

    t = time.perf_counter()
    df = cudf.read_parquet(data_path)
    lookup = cudf.read_parquet(lookup_path)
    timings["load_s"] = round(time.perf_counter() - t, 3)
    n_input = len(df)

    t = time.perf_counter()
    df = df[(df["Status"] == "live") & (df["Bases"] > 0)]
    timings["filter_s"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    df = df.merge(lookup, on="Center", how="left")
    timings["join_s"] = round(time.perf_counter() - t, 3)

    df["year"] = cudf.to_datetime(df["Published"]).dt.year

    t = time.perf_counter()
    agg = (df.groupby(["Center", "technology", "year"])
             .agg({"Bases": ["sum", "mean"], "Accession": "count"})
             .reset_index())
    agg.columns = ["Center", "technology", "year",
                   "total_bases", "mean_bases", "run_count"]
    timings["agg_s"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    agg = agg.sort_values(["technology", "year"])
    agg["cumulative_bases"] = (agg.groupby("technology")["total_bases"]
                                  .cumsum())
    agg.to_parquet(f"{out_dir}/gpu_{scale}_result.parquet", index=False)
    timings["window_s"] = round(time.perf_counter() - t, 3)

    total_s = sum(timings.values())
    result = {
        "approach": "gpu_cudf",
        "gpu_available": GPU_AVAILABLE,
        "scale": scale,
        "n_input": n_input,
        "total_s": round(total_s, 3),
        "throughput_M_rows_per_s": round(n_input / total_s / 1e6, 3),
        **timings,
    }
    Path(f"{out_dir}/gpu_{scale}.json").write_text(json.dumps(result, indent=2))
    print(f"gpu | {scale} | {n_input:,} rows | {total_s:.1f}s | "
          f"{result['throughput_M_rows_per_s']} M rows/s")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",   default="data/sra_runs_10M.parquet")
    parser.add_argument("--lookup", default="data/platform_lookup.parquet")
    parser.add_argument("--out",    default="results")
    args = parser.parse_args()
    run_pipeline(args.data, args.lookup, args.out)
