#!/bin/bash
#SBATCH --account=uppmax2026-1-11
#SBATCH --partition=pelle
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=20
#SBATCH --mem=192G
#SBATCH --time=02:00:00
#SBATCH --job-name=sra-spark-benchmark
#SBATCH --output=%j_spark.out
#SBATCH --error=%j_spark.err
#SBATCH --mail-type=END,FAIL

# =============================================================================
# SRA Spark benchmark — UPPMAX (Pelle)
# Allocation: uppmax2026-1-11
# Submit from repo root: sbatch p3-spark-benchmark/jobs/uppmax_spark.sh
# Monitor: squeue -u $USER
#
# How it works:
# SLURM allocates 4 nodes. We then start a Spark standalone cluster on those
# nodes using srun (SLURM-native, no SSH needed). The master runs on the first
# node; workers run on all 4 nodes. spark-submit connects to the master URL.
# =============================================================================

set -euo pipefail

echo "Job $SLURM_JOB_ID started on $SLURM_NODELIST at $(date)"

module load Java/17.0.15

# SLURM_SUBMIT_DIR = directory where sbatch was called (repo root = <base>/portfolio)
REPO_DIR=$SLURM_SUBMIT_DIR
PROJECT=$(cd "$REPO_DIR/.." && pwd)
CODE=$REPO_DIR/p3-spark-benchmark

export SPARK_HOME=$PROJECT/tools/spark-3.5.8-bin-hadoop3
export PATH=$SPARK_HOME/bin:$PATH
DATA=$PROJECT/p3/data
RESULTS=$PROJECT/p3/results

mkdir -p "$RESULTS"

# ---------------------------------------------------------------------------
# Start Spark standalone cluster using srun (SLURM-native, no SSH required)
# $SLURM_NODELIST is compact notation — expand with scontrol
NODES=($(scontrol show hostname "$SLURM_NODELIST"))
MASTER=${NODES[0]}
MASTER_URL="spark://$MASTER:7077"

echo "Starting Spark master on $MASTER"
srun --nodes=1 --ntasks=1 -w "$MASTER" \
    "$SPARK_HOME/bin/spark-class" org.apache.spark.deploy.master.Master \
    --host "$MASTER" --port 7077 &
sleep 10

echo "Starting Spark workers on all nodes"
for node in "${NODES[@]}"; do
    srun --nodes=1 --ntasks=1 -w "$node" \
        "$SPARK_HOME/bin/spark-class" org.apache.spark.deploy.worker.Worker \
        "$MASTER_URL" &
done
sleep 15
echo "Spark cluster ready at $MASTER_URL"

# ---------------------------------------------------------------------------
pip install --user -q pyarrow pandas 2>/dev/null

# ---- Run at each scale and node count --------------------------------------

for SCALE in 10M 40M; do
    DATA_FILE=$DATA/sra_runs_${SCALE}.parquet

    for N_NODES in 1 2 4; do
        echo "--- Spark | $SCALE | $N_NODES nodes ---"

        spark-submit \
            --master "$MASTER_URL" \
            --deploy-mode client \
            --num-executors $N_NODES \
            --executor-cores 20 \
            --executor-memory 48g \
            --driver-memory 16g \
            --conf spark.sql.shuffle.partitions=$((N_NODES * 40)) \
            "$CODE/src/pipeline_spark.py" \
            --data "$DATA_FILE" \
            --lookup "$DATA/platform_lookup.parquet" \
            --out "$RESULTS" \
            --nodes $N_NODES
    done
done

# ---------------------------------------------------------------------------
echo "Stopping Spark cluster"
srun --nodes=1 --ntasks=1 -w "$MASTER" \
    "$SPARK_HOME/bin/spark-class" org.apache.spark.deploy.master.Master --stop 2>/dev/null || true

echo "All runs complete at $(date)"
echo "Results in: $RESULTS"
