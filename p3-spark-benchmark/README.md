# P3 — Spark Benchmark

Benchmarks three processing approaches on the same ETL pipeline using real
NCBI SRA metadata — the sequencing run catalog used across all major genomics
archives worldwide.

## What is being benchmarked?

| Approach | Runtime | Hardware | Where |
|----------|---------|----------|-------|
| Pandas | Single-node, in-memory | Laptop / local | Local |
| PySpark | Distributed | UPPMAX (Rackham) | HPC via SLURM |
| GPU / cuDF | GPU-accelerated | Dardel (AMD MI250X, ROCm) | HPC via SLURM |

Same pipeline, same data, three runtimes. The goal is to measure crossover
points — where Spark and GPU justify their operational complexity over pandas.

## Dataset — NCBI SRA Metadata

Source: `https://ftp.ncbi.nlm.nih.gov/sra/reports/Metadata/SRA_Accessions.tab`

- Updated daily by NCBI
- Full file: ~32 GB uncompressed, ~40M RUN records
- No authentication required
- Directly relevant to SciLifeLab workflows — SRA is the primary archive
  for sequencing data from genomics, transcriptomics, metagenomics etc.

**Data fetch performance (observed 2026-04-29):**
- Streaming 1M RUN records: ~192 seconds over NCBI FTP (~0.17 GB transferred)
- NCBI FTP throughput: ~0.9 MB/s (typical, rate-limited by NCBI)
- Full 40M records estimated: ~2–3 hours streaming; better to fetch on HPC
  directly from `/proj/nbis_support/portfolio/p3/data/` once staged

**Columns used:** Accession, Status, Published, Center, Spots, Bases, BioProject

**Pipeline:**
```
Filter    → Status=live, Bases > 0
Join      → broadcast-join with platform_lookup on Center (adds technology, region)
Aggregate → group by (Center, technology, year) → total/mean Bases, run count
Window    → cumulative bases per technology per year
Output    → Parquet + timing JSON
```

## Quick start (local)

```bash
pip install -r requirements.txt

# Fetch 1M rows (~3 min, streams from NCBI)
python src/fetch_data.py --sample 1M --out data/

# Run pandas baseline
python src/pipeline_pandas.py --data data/sra_runs_1M.parquet --out results/
```

## HPC runs

```bash
# UPPMAX (Spark, 1/2/4 nodes, 10M + 40M rows)
sbatch jobs/uppmax_spark.sh

# Dardel (cuDF GPU, 10M + 40M rows)
sbatch jobs/dardel_gpu.sh
```

Data is pre-staged at `/proj/nbis_support/portfolio/p3/data/` on both clusters.

## Project structure

```
src/
  fetch_data.py          Stream SRA metadata from NCBI, save as Parquet
  pipeline_pandas.py     Baseline pipeline
  pipeline_spark.py      PySpark pipeline (UPPMAX)
  pipeline_gpu.py        cuDF pipeline (Dardel, ROCm)
jobs/
  uppmax_spark.sh        SLURM — Rackham, 1/2/4 nodes, 10M + 40M rows
  dardel_gpu.sh          SLURM — Dardel GPU partition, 10M + 40M rows
data/                    Local data (gitignored)
results/                 Timing JSONs + benchmark_table.csv
notebooks/
  benchmark_pipeline.ipynb   Speedup plots and analysis
docs/
  q8-hpc-narrative.md    HPC experience writeup with real numbers
```
