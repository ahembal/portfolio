"""
Pandas baseline pipeline — single-node, in-memory.

Pipeline:
  1. Filter:    keep live RUN records with Bases > 0
  2. Join:      broadcast-join with platform_lookup on Center
  3. Aggregate: group by (Center, technology, year) → sum/mean/count of Bases
  4. Window:    cumulative total bases per technology by year
  5. Output:    Parquet + timing JSON

Usage:
    python src/pipeline_pandas.py --data data/sra_runs_10M.parquet --out results/
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd


def run_pipeline(data_path: Path, lookup_path: Path, out_dir: Path) -> dict:
    scale = data_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    timings = {}

    t = time.perf_counter()
    df = pd.read_parquet(data_path)
    lookup = pd.read_parquet(lookup_path)
    timings["load_s"] = round(time.perf_counter() - t, 3)
    n_input = len(df)

    t = time.perf_counter()
    df = df[(df["Status"] == "live") & (df["Bases"] > 0)].copy()
    timings["filter_s"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    df = df.merge(lookup, on="Center", how="left")
    timings["join_s"] = round(time.perf_counter() - t, 3)

    df["year"] = df["Published"].dt.year

    t = time.perf_counter()
    agg = (df.groupby(["Center", "technology", "year"], observed=True)
             .agg(
                 total_bases=("Bases", "sum"),
                 mean_bases=("Bases", "mean"),
                 run_count=("Accession", "count"),
             )
             .reset_index())
    timings["agg_s"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    agg = agg.sort_values(["technology", "year"])
    agg["cumulative_bases"] = (agg.groupby("technology", observed=True)["total_bases"]
                                  .cumsum())
    timings["window_s"] = round(time.perf_counter() - t, 3)

    agg.to_parquet(out_dir / f"pandas_{scale}_result.parquet", index=False)

    total_s = sum(timings.values())
    result = {
        "approach": "pandas",
        "scale": scale,
        "n_input": n_input,
        "n_output": len(agg),
        "total_s": round(total_s, 3),
        "throughput_M_rows_per_s": round(n_input / total_s / 1e6, 3),
        **timings,
    }
    (out_dir / f"pandas_{scale}.json").write_text(json.dumps(result, indent=2))
    print(f"pandas | {scale} | {n_input:,} rows | {total_s:.1f}s | "
          f"{result['throughput_M_rows_per_s']} M rows/s")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",   default="data/sra_runs_10M.parquet")
    parser.add_argument("--lookup", default="data/platform_lookup.parquet")
    parser.add_argument("--out",    default="results")
    args = parser.parse_args()
    run_pipeline(Path(args.data), Path(args.lookup), Path(args.out))
