# How the Benchmark Works — P3 Spark
*Last updated: 2026-05-03*

This document explains the benchmark pipeline, what each step does, how the
three runtimes differ, and how to read the results.

---

## The big picture

Same question, three answers:

```
NCBI SRA metadata (40M sequencing run records)
        │
        ▼
The same ETL pipeline in three runtimes:

  Pandas  ─────────────────────────  single laptop/node
  PySpark ─────────────────────────  distributed across HPC nodes (UPPMAX Pelle)
  cuDF    ─────────────────────────  GPU-accelerated (Dardel AMD MI250X)
        │
        ▼
Results: wall time, throughput (M rows/s), per-step breakdown
        │
        ▼
Question answered: at what data scale does each approach justify its complexity?
```

---

## The dataset

**Source:** NCBI SRA (Sequence Read Archive) metadata
**URL:** `https://ftp.ncbi.nlm.nih.gov/sra/reports/Metadata/SRA_Accessions.tab`

This is the catalog of every sequencing run deposited to the world's major
genomics archives (NCBI, EBI, DDBJ). Updated daily. No authentication needed.

**Why this dataset and not synthetic data?**
Synthetic data is predictable — it doesn't have the skewed distributions,
missing values, and irregular patterns that real data has. SRA metadata is
real-world: a few large sequencing centers dominate, base counts span 6 orders
of magnitude, many fields are null. A benchmark on real data is more credible
than one on `numpy.random.normal()`.

**Columns used:**

| Column | Type | What it contains |
|--------|------|-----------------|
| Accession | string | SRA run ID (SRR/ERR/DRR prefix) |
| Status | category | `live` / `suppressed` / `unpublished` |
| Published | datetime | When the run became publicly available |
| Center | category | Submitting institution (e.g. GEO, BGI, BROAD) |
| Bases | integer | Total nucleotide bases in the run |
| BioProject | string | Parent project accession |

**Scales used:**

| Scale | Rows | Approx size |
|-------|------|------------|
| 1M | 1,000,000 | ~170 MB Parquet |
| 10M | 10,000,000 | ~1.7 GB Parquet |
| 40M | 40,000,000 | ~6.8 GB Parquet |

---

## What kind of workload is this?

This benchmark covers an **OLAP (Online Analytical Processing)** workload — the
standard pattern in data engineering and research pipelines:

- Scan large amounts of historical records
- Filter down to relevant rows
- Group and aggregate (sum, count, average)
- Compute trends over time (window functions)

This is distinct from **OLTP (Online Transaction Processing)** which handles
individual writes like "insert this record" or "update this status". OLTP is
what your web API database does. OLAP is what your analytics, dashboards,
and research pipelines do.

| Engine | Designed for | Sweet spot |
|--------|-------------|-----------|
| Pandas | General purpose | < 5M rows, single machine |
| DuckDB | OLAP, single node | 1M – 1B rows, no cluster needed |
| PySpark | OLAP, distributed | > 100M rows, multi-node, fault tolerance |
| cuDF | OLAP, GPU | GPU available, vectorisable operations |

---

## Why not DuckDB?

DuckDB is an in-process analytical database that has become the default
recommendation for OLAP workloads at 1M–1B row scale on a single node.
It is often 5–10× faster than Pandas and competitive with Spark at medium
scale — without any cluster setup.

A complete benchmark would include DuckDB as a fourth engine — it would give
a more honest answer to "when should you reach for Spark vs a simpler tool?".
It is listed as a future addition in PROGRESS.md. The current three-way
comparison (Pandas / Spark / cuDF) covers the single-node vs multi-node vs
GPU axes. DuckDB would add the modern single-node reference point.

---

## The pipeline — step by step

All three runtimes execute the exact same logical pipeline. The only difference
is which library executes each step.

### Step 1 — Filter

```python
df = df[(df["Status"] == "live") & (df["Bases"] > 0)]
```

Keeps only active runs with valid base counts. Removes suppressed, unpublished,
and zero-base records (~10% of rows removed).

**Why this step is cheap:**
Filter is a scan — each row is checked independently. All three runtimes handle
this well. Pandas does it in-memory, Spark partitions the data across executors,
cuDF runs vectorised kernel on GPU.

---

### Step 2 — Broadcast join

```python
df = df.merge(platform_lookup, on="Center", how="left")
```

Enriches each run record with its technology type (`short-read`, `long-read`)
and region. The lookup table has 10 rows.

**What "broadcast" means:**
In a distributed system (Spark), joining two large tables requires shuffling
data across the network — expensive. When one table is tiny (10 rows), it is
cheaper to copy it to every executor (`broadcast`) rather than shuffle the
large table. The broadcast hint `F.broadcast(lookup)` tells Spark to do this.

Without the broadcast hint, Spark would default to a sort-merge join —
potentially 10× slower on this step.

In pandas and cuDF this is a regular in-memory merge — no network involved.

---

### Step 3 — Aggregate

```python
agg = df.groupby(["Center", "technology", "year"]).agg(
    total_bases=("Bases", "sum"),
    mean_bases=("Bases", "mean"),
    run_count=("Accession", "count"),
)
```

Groups by submitting center, technology type, and year of publication.
Computes total bases submitted, mean bases per run, and number of runs.

**This is the most expensive step in Spark.**
GroupBy in a distributed system requires a shuffle — all rows with the same
key must be sent to the same executor across the network. This is O(data size)
in network I/O. At 40M rows, this is where Spark's overhead becomes visible.

In pandas, groupby is an in-memory hash table operation — fast at 1-10M rows,
slow at 40M+.
In cuDF, groupby runs as a parallel kernel on GPU HBM — fast across all scales.

---

### Step 4 — Window (cumulative sum)

```python
agg["cumulative_bases"] = agg.groupby("technology")["total_bases"].cumsum()
```

Computes the running total of bases submitted per technology type, ordered by
year. Shows how sequencing output has grown over time.

**This is inherently sequential.**
Cumulative sum requires knowing the value at position N-1 before computing
position N. Even on GPU, this cannot be fully parallelised. This step limits
how much GPU acceleration helps overall.

---

### Step 5 — Output

Each runtime writes two outputs:
- **Parquet file** — the aggregated result (small, a few thousand rows)
- **JSON timing file** — wall time and per-step breakdown

---

## How the three runtimes differ

| | Pandas | PySpark | cuDF |
|--|--------|---------|------|
| Where data lives | RAM | Distributed across nodes | GPU HBM |
| Parallelism | Single CPU core | Multiple nodes × multiple cores | Thousands of GPU cores |
| Filter speed | Fast (vectorised) | Fast (partition-parallel) | Fastest (HBM bandwidth) |
| Join speed | Fast | Fast (with broadcast hint) | Fast |
| GroupBy speed | Fast to 10M, slow at 40M | Slow (shuffle) | Very fast |
| Window speed | Sequential | Sequential per partition | Mostly sequential |
| Startup overhead | None | ~30s cluster startup | ~2s CUDA/ROCm init |
| Operational cost | None | SLURM allocation, module loading | SLURM GPU allocation |

---

## How to read the results

After all runs complete, `results/benchmark_table.csv` contains one row per
(approach, scale, nodes) combination:

| Column | Meaning |
|--------|---------|
| `approach` | `pandas`, `spark`, `gpu_cudf` |
| `scale` | dataset scale label |
| `nodes` | number of Spark executor nodes (1/2/4), always 1 for pandas/GPU |
| `total_s` | total wall time in seconds |
| `throughput_M_rows_per_s` | input rows processed per second (millions) |
| `load_s` | time to read Parquet from disk |
| `filter_s` | time for the filter step |
| `join_s` | time for the broadcast join |
| `agg_s` | time for the groupby aggregate |
| `window_s` | time for the cumulative sum |

**The key comparison:**
- At 1M rows: pandas is fastest (no startup overhead)
- At 10M rows: crossover zone — Spark and GPU begin to compete
- At 40M rows: GPU wins for filter/agg, Spark wins when data doesn't fit in RAM

**Spark scaling efficiency:**
At 4 nodes vs 1 node, ideal speedup is 4×. Real speedup is ~3.2× due to shuffle
network overhead. The gap from ideal tells you how much the workload is network-bound.

---

## Limitations

| Limitation | Impact |
|-----------|--------|
| Single benchmark run per config | No variance estimate — one slow job looks bad |
| Parquet already on local disk | Doesn't measure S3/Lustre I/O which is the bottleneck in real HPC workflows |
| Small output table | The aggregate is tiny — output write time is negligible here but not in real pipelines |
| cuDF on ROCm (AMD) not CUDA | Some cuDF features differ slightly from the CUDA version |
| Results depend on queue wait time | SLURM queue variation not captured in wall time |
