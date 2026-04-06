#!/bin/bash
#SBATCH --account=naiss2026-4-384
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --time=01:00:00
#SBATCH --job-name=pcam-train
#SBATCH --output=%j_pcam_train.out
#SBATCH --error=%j_pcam_train.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=emre.balsever@liu.se

# =============================================================================
# PatchCamelyon training job — Dardel GPU (AMD MI250X)
# Allocation: NAISS 2026/4-384 (NBIS support)
# Scope: benchmarking ML approaches for bioimage analysis
#
# Usage:
#   sbatch submit_dardel.sh
#
# Monitor:
#   squeue -u emre.balsever
#   jobinfo <job_id>
#
# Output artifacts are written to $OUTPUT_DIR on Crex (nbis_support).
# After the job completes, run push_artifacts.py to transfer to Ceph RGW.
# =============================================================================

set -euo pipefail

echo "============================================"
echo "Job ID:       $SLURM_JOB_ID"
echo "Node:         $SLURM_NODELIST"
echo "GPUs:         $SLURM_GPUS"
echo "Start:        $(date)"
echo "============================================"

# --- Environment -------------------------------------------------------------

module load PyTorch/2.3.1-rocm-6.0

# HuggingFace cache on Crex — avoids re-downloading across jobs
export HF_DATASETS_CACHE=/proj/nbis_support/portfolio/hf_cache

# Training configuration — override defaults in train.py
export OUTPUT_DIR=/proj/nbis_support/portfolio/checkpoints/$SLURM_JOB_ID
export EPOCHS=5
export BATCH_SIZE=128
export LEARNING_RATE=1e-4
export NUM_WORKERS=4

mkdir -p "$OUTPUT_DIR"
mkdir -p "$HF_DATASETS_CACHE"

# --- Install dependencies ----------------------------------------------------
# Using --user install since we don't have a venv on the compute node.
# pip-compile generated requirements.txt ensures pinned reproducible deps.

pip install --user -q -r /proj/nbis_support/portfolio/code/p1-pcam-deployment/requirements.txt

# --- Run training -------------------------------------------------------------

cd /proj/nbis_support/portfolio/code/p1-pcam-deployment

python train/train.py

echo "============================================"
echo "Training complete: $(date)"
echo "Artifacts in:     $OUTPUT_DIR"
echo "============================================"

# --- Push artifacts to Ceph RGW on turtle ------------------------------------
# Transfers best_model.pt, final_model.pt, metrics.json, config.json
# to s3://ml-artifacts/pcam/$SLURM_JOB_ID/ via boto3.
# Requires RGW credentials in environment — set in ~/.bash_profile on Dardel.

python train/push_artifacts.py \
    --source-dir "$OUTPUT_DIR" \
    --bucket     ml-artifacts \
    --prefix     pcam/$SLURM_JOB_ID

echo "Artifacts pushed to RGW. Job done."
