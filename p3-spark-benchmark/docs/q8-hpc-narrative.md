# Q8 — HPC and Large-Scale Data Processing

> Numbers in `[brackets]` are placeholders — filled after UPPMAX/Dardel runs complete.

## The question this project answers

When does the operational overhead of distributed computing pay off?
Pandas is simpler, Spark is scalable, GPU is fast — but none of these are
universally true. The answer depends on data scale, pipeline shape, and
available infrastructure.

---

## Infrastructure

### UPPMAX — Pelle
CPU cluster operated by Uppsala University. Used for Spark runs.

- Nodes: 128 cores, 256 GB RAM per node
- Storage: Crex (Lustre, shared with Dardel via `/proj/nbis_support/`)
- Scheduler: SLURM
- Modules used: `java/17`, `spark/3.5.0`
- Allocation: `UPPMAX 2026/1-11` (NBIS support)

### PDC Dardel
GPU/CPU cluster at KTH. Used for cuDF GPU runs.

- GPU nodes: AMD MI250X (128 GB HBM per GCD)
- Backend: ROCm — AMD hardware, important distinction from typical NVIDIA/CUDA setup
- Scheduler: SLURM
- Modules used: `RAPIDS/24.06-rocm-6.0-python-3.11`
- Allocation: `naiss2026-4-384`

---

## The pipeline

Same ETL logic on all three runtimes, applied to real NCBI SRA run metadata:

```
Filter    → Status=live, Bases > 0           (~90% pass rate)
Join      → broadcast platform_lookup         (10-row table, no shuffle)
Aggregate → (Center, technology, year)        shuffle-heavy step in Spark
Window    → cumulative bases per technology   sequential dependency
```

---

## Results

### Pandas baseline (local)

| Scale | Rows | Total time | Throughput |
|-------|------|-----------|------------|
| 1M  | 1,000,000 | 1.1 s | 0.94 M rows/s |
| 10M | [N] | [X] s | [X] M rows/s |

Timing breakdown at 1M: load=0.55s, filter=0.23s, join=0.16s, agg=0.12s, window=0.002s.
Parquet read dominates at small scale — actual compute is < 0.5s.

### Spark on UPPMAX (Rackham)

| Scale | Nodes | Total time | Speedup vs pandas |
|-------|-------|-----------|------------------|
| 10M | 1 | [X] s | [X]x |
| 10M | 2 | [X] s | [X]x |
| 10M | 4 | [X] s | [X]x |
| 40M | 1 | [X] s | [X]x |
| 40M | 4 | [X] s | [X]x |

### GPU / cuDF on Dardel (MI250X)

| Scale | Total time | Speedup vs pandas |
|-------|-----------|------------------|
| 10M | [X] s | [X]x |
| 40M | [X] s | [X]x |

---

## Analysis

### Why Spark's shuffle is the bottleneck

The `groupBy` aggregate triggers a shuffle — all rows with the same key must
reach the same executor. At small scales this network cost exceeds the
parallelism benefit. 1-node Spark is slower than pandas at 10M rows.
The broadcast join avoids shuffling the lookup table entirely.

### Why the GPU wins on columnar aggregation

cuDF operates on data in GPU HBM (~[X] GB/s bandwidth vs ~50 GB/s for DDR5).
Filter and aggregate run as vectorised kernels across all ROCm compute units.
The window/cumsum step is inherently sequential — this limits the GPU advantage
on this specific pipeline to [X]x rather than the theoretical maximum.

### Crossover points

| Transition | Worth it above |
|------------|----------------|
| Pandas to Spark | [X]M rows |
| Pandas to GPU   | [X]M rows |

---

## HPC operational notes

**What worked well:**
- SLURM job submission and monitoring (`squeue`, `jobinfo`)
- Module system for reproducible environments without containers
- Lustre filesystem (`/proj/nbis_support/`) visible from all compute nodes

**Friction encountered:**
- NCBI FTP rate-limited to ~0.9 MB/s — large datasets must be staged on HPC
- Dardel uses ROCm (AMD), not CUDA — RAPIDS module name differs from NVIDIA setups
- SLURM queue wait: [X] min on Rackham, [X] min on Dardel GPU partition
