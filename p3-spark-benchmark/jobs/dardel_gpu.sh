#!/bin/bash
#SBATCH --account=naiss2026-4-384
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --time=01:00:00
#SBATCH --job-name=sra-gpu-benchmark
#SBATCH --output=%j_gpu.out
#SBATCH --error=%j_gpu.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=emre.balsever@liu.se

# =============================================================================
# SRA GPU benchmark — Dardel (AMD MI250X, ROCm)
# Allocation: NAISS 2026/4-384
#
# cuDF with ROCm backend — same pipeline as pandas/spark.
# MI250X has 128 GB HBM — 40M rows (~8 GB) fits comfortably.
#
# Submit:  sbatch jobs/dardel_gpu.sh
# Monitor: squeue -u emre.balsever
# =============================================================================

set -euo pipefail

echo "Job $SLURM_JOB_ID started on $SLURM_NODELIST at $(date)"

module load RAPIDS/24.06-rocm-6.0-python-3.11

PROJECT=/proj/nbis_support/portfolio
CODE=$PROJECT/code/p3-spark-benchmark
DATA=$PROJECT/p3/data
RESULTS=$PROJECT/p3/results

mkdir -p "$RESULTS"

# Fetch data if not present
for SCALE in 10M 40M; do
    DATA_FILE=$DATA/sra_runs_${SCALE}.parquet
    if [ ! -f "$DATA_FILE" ]; then
        echo "Fetching $SCALE data..."
        python "$CODE/src/fetch_data.py" --sample $SCALE --out "$DATA"
    fi

    echo "--- GPU | $SCALE ---"
    python "$CODE/src/pipeline_gpu.py" \
        --data   "$DATA_FILE" \
        --lookup "$DATA/platform_lookup.parquet" \
        --out    "$RESULTS"
done

echo "All runs complete at $(date)"
echo "Results in: $RESULTS"
