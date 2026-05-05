"""
PySpark pipeline — distributed on UPPMAX via SLURM.
Identical logic to pipeline_pandas.py, verified by output diff.

Usage (local):
    spark-submit src/pipeline_spark.py --data data/sra_runs_10M.parquet --out results/

Usage (UPPMAX):
    sbatch jobs/uppmax_spark.sh
"""

import argparse
import json
import time
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


def run_pipeline(data_path: str, lookup_path: str, out_dir: str,
                 nodes: int = 1) -> dict:
    scale = Path(data_path).stem
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    spark = (SparkSession.builder
             .appName(f"sra-benchmark-{scale}")
             .config("spark.sql.shuffle.partitions", "200")
             .config("spark.sql.legacy.parquet.nanosAsLong", "true")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    timings = {}
    t = time.perf_counter()
    df = spark.read.parquet(data_path)
    lookup = spark.read.parquet(lookup_path)
    lookup_bc = F.broadcast(lookup)           # broadcast hint — avoids shuffle
    timings["load_s"] = round(time.perf_counter() - t, 3)
    n_input = df.count()

    t = time.perf_counter()
    df = df.filter((F.col("Status") == "live") & (F.col("Bases") > 0))
    timings["filter_s"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    df = df.join(lookup_bc, on="Center", how="left")
    timings["join_s"] = round(time.perf_counter() - t, 3)

    df = df.withColumn("year", F.year("Published"))

    t = time.perf_counter()
    agg = (df.groupBy("Center", "technology", "year")
             .agg(
                 F.sum("Bases").alias("total_bases"),
                 F.mean("Bases").alias("mean_bases"),
                 F.count("Accession").alias("run_count"),
             ))
    timings["agg_s"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    w = Window.partitionBy("technology").orderBy("year").rowsBetween(
        Window.unboundedPreceding, 0)
    agg = agg.withColumn("cumulative_bases", F.sum("total_bases").over(w))
    agg.write.mode("overwrite").parquet(f"{out_dir}/spark_{scale}_result.parquet")
    timings["window_s"] = round(time.perf_counter() - t, 3)

    spark.stop()

    total_s = sum(timings.values())
    result = {
        "approach": "spark",
        "scale": scale,
        "nodes": nodes,
        "n_input": n_input,
        "total_s": round(total_s, 3),
        "throughput_M_rows_per_s": round(n_input / total_s / 1e6, 3),
        **timings,
    }
    Path(f"{out_dir}/spark_{scale}_{nodes}nodes.json").write_text(
        json.dumps(result, indent=2))
    print(f"spark | {scale} | {nodes} nodes | {n_input:,} rows | {total_s:.1f}s | "
          f"{result['throughput_M_rows_per_s']} M rows/s")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",   default="data/sra_runs_10M.parquet")
    parser.add_argument("--lookup", default="data/platform_lookup.parquet")
    parser.add_argument("--out",    default="results")
    parser.add_argument("--nodes",  type=int, default=1)
    args = parser.parse_args()
    run_pipeline(args.data, args.lookup, args.out, args.nodes)
