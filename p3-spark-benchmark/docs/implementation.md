# Implementation Notes — P3 Spark Benchmark
*Last updated: 2026-04-28*

This document describes how the project was built: structure chosen, problems hit during development, and decisions made along the way. For how the finished product works see `how-it-works.md`. For data source details see `data-source.md`.

---

## src/fetch_data.py
- Streams NCBI SRA metadata via the SRA cloud metadata endpoint (TSV format)
- No authentication needed — SRA metadata is public
- Fetches 1M rows in ~192s locally; expected to be faster on HPC with better network
- Writes to Parquet for efficient columnar loading by downstream pipelines
- Key fields used: run_accession, spots, bases, platform, center_name, release_date, status

## src/pipeline_pandas.py
- Pipeline: filter (status=live AND bases>0) → broadcast join with platform_lookup (small dict) → groupby aggregate (center_name, technology, year) → cumulative sum window
- Writes two outputs: results Parquet and timing JSON (load_s, compute_s, total_s, rows_per_s)
- Local result at 1M rows: total=1.1s, load=0.55s, compute=0.51s, 0.94 M rows/s

## src/pipeline_spark.py
- Identical query logic to pandas — same filter, join, aggregate, window
- SparkSession configured with: spark.sql.shuffle.partitions tuned per node count (2 × cores), broadcast hint on platform_lookup join
- Output format identical to pandas (same Parquet schema, same timing JSON keys) — enables automated diff for correctness checking

## src/pipeline_gpu.py
- Uses cuDF (RAPIDS) with ROCm backend for AMD MI250X on Dardel
- Falls back to pandas if cuDF is not available (import guard) — allows local testing on CPU
- Same pipeline logic as pandas and Spark — three engines, one pipeline definition

## jobs/uppmax_spark.sh
- Account: naiss2026-4-384, cluster: Rackham (UPPMAX)
- Runs at 1, 2, and 4 nodes for both 10M and 40M row inputs — 6 SLURM job steps total
- Module: spark/3.x (loaded from UPPMAX module system)
- Output: results/spark_sra_runs_{size}_{nodes}nodes.json

## jobs/dardel_gpu.sh
- Account: naiss2026-4-384, cluster: Dardel (PDC KTH)
- Module: RAPIDS/24.06-rocm-6.0
- Runs 10M and 40M row inputs — 2 job steps
- Output: results/gpu_sra_runs_{size}.json

## Known issues / pending
- Dardel Klemming storage was 94% full (~29 GB free) when last checked — input data files may not fit without cleanup
- HPC jobs not yet submitted as of 2026-04-28 — SSH to Dardel is working
