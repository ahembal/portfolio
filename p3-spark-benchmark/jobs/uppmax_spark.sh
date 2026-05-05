#!/bin/bash
#SBATCH --account=UPPMAX-2026-1-11
#SBATCH --partition=node
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=20
#SBATCH --mem=192G
#SBATCH --time=02:00:00
#SBATCH --job-name=sra-spark-benchmark
#SBATCH --output=%j_spark.out
#SBATCH --error=%j_spark.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=emre.balsever@scilifelab.se

# =============================================================================
# SRA Spark benchmark — UPPMAX (Pelle)
# Allocation: UPPMAX 2026/1-11 (NBIS support)
# Login: pelle.uppmax.uu.se
#
# Runs pipeline at 10M and 40M rows with 1, 2, and 4 nodes.
# Results written to <base>/p3/results/ (derived from script location)
#
# Submit:  sbatch jobs/uppmax_spark.sh
# Monitor: squeue -u $USER
# =============================================================================

set -euo pipefail

echo "Job $SLURM_JOB_ID started on $SLURM_NODELIST at $(date)"

module load Java/17.0.15

# Derive directories from script location — no manual PROJECT variable needed.
# Layout: <base>/portfolio/p3-spark-benchmark/jobs/uppmax_spark.sh
#         <base>/tools/spark-3.5.8-bin-hadoop3/
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT=$(cd "$SCRIPT_DIR/../../.." && pwd)   # <base>/portfolio → <base>
CODE=$PROJECT/portfolio/p3-spark-benchmark

# Spark installed manually — no module available on Pelle (as of 2026-05-05)
export SPARK_HOME=$PROJECT/tools/spark-3.5.8-bin-hadoop3
export PATH=$SPARK_HOME/bin:$PATH
DATA=$PROJECT/p3/data
RESULTS=$PROJECT/p3/results

mkdir -p "$RESULTS"

pip install --user -q pyarrow pandas 2>/dev/null

# ---- Run at each scale and node count ----------------------------------------

for SCALE in 10M 40M; do
    DATA_FILE=$DATA/sra_runs_${SCALE}.parquet
    if [ ! -f "$DATA_FILE" ]; then
        echo "Fetching $SCALE data..."
        python "$CODE/src/fetch_data.py" --sample $SCALE --out "$DATA"
    fi

    for N_NODES in 1 2 4; do
        echo "--- Spark | $SCALE | $N_NODES nodes ---"
        EXECUTOR_CORES=20
        EXECUTOR_MEM=48g
        DRIVER_MEM=16g

        spark-submit \
            --master spark://$SLURM_NODELIST:7077 \
            --deploy-mode client \
            --num-executors $N_NODES \
            --executor-cores $EXECUTOR_CORES \
            --executor-memory $EXECUTOR_MEM \
            --driver-memory $DRIVER_MEM \
            --conf spark.sql.shuffle.partitions=$((N_NODES * 40)) \
            "$CODE/src/pipeline_spark.py" \
            --data "$DATA_FILE" \
            --lookup "$DATA/platform_lookup.parquet" \
            --out "$RESULTS" \
            --nodes $N_NODES
    done
done

echo "All runs complete at $(date)"
echo "Results in: $RESULTS"
