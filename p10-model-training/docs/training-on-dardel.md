# Training on Dardel
*p10 — Model Training & Benchmarking*

Dardel (KTH, Stockholm) is the primary compute resource for p10. This document
covers everything needed to go from a fresh login to a running training job.

---

## Prerequisites

- Active NAISS/SNIC allocation on Dardel with GPU node access
- BEETLE tiles already generated and transferred to Dardel scratch
- SSH key configured for Dardel login (`ssh <username>@dardel.pdc.kth.se`)

---

## Storage layout on Dardel

```
$SCRATCH/p10/                    ← Lustre scratch (fast, no backup, purged after 30 days)
  data/
    raw/wsis/                    ← downloaded BEETLE WSIs (large, re-downloadable)
    raw/masks/                   ← BEETLE annotation masks
    tiles/                       ← output of data/pipeline.py (~90 GB)
  runs/                          ← training checkpoints and metrics

$HOME/repos/portfolio/           ← code (backed up via git, not scratch)
  p10-model-training/
```

Use `$SCRATCH` for all data and model outputs. Scratch is on Lustre — fast
parallel I/O, appropriate for DataLoader workers reading many small PNG files.
Do not use `$HOME` for data (quota: 25 GB).

To check your scratch quota: `lfs quota -u $USER /cfs/klemming`

---

## Environment setup

Dardel uses modules for software management. Load the required modules and
create a virtual environment once:

```bash
# Load modules
module load PDC
module load Python/3.11.3-cpeGNU-23.03
module load CUDA/12.2.0

# Create environment (once)
python -m venv $HOME/envs/p10
source $HOME/envs/p10/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Install PyTorch with CUDA support (check for compatible version at launch time)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

Activate the environment at the start of every session:
```bash
module load PDC Python/3.11.3-cpeGNU-23.03 CUDA/12.2.0
source $HOME/envs/p10/bin/activate
```

---

## Data transfer to Dardel

Transfer tiles from the local machine or another cluster:

```bash
# From local machine to Dardel scratch
rsync -avh --progress \
  data/tiles/ \
  <username>@dardel.pdc.kth.se:/cfs/klemming/scratch/<username>/p10/data/tiles/

# Transfer raw WSIs (large — use nohup or screen)
rsync -avh --progress \
  data/raw/ \
  <username>@dardel.pdc.kth.se:/cfs/klemming/scratch/<username>/p10/data/raw/
```

If tiling on Dardel directly (preferred for large datasets — avoids transferring
1.4 TB of raw WSIs):
```bash
# Run the data pipeline on a Dardel CPU node
sbatch jobs/tile.job
```

See `jobs/tile.job` (to be created) for the SLURM script.

---

## SLURM job scripts

### Single-GPU training job

```bash
#!/bin/bash
#SBATCH -A <your-project-allocation>
#SBATCH -J p10-train
#SBATCH -p gpu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --gpus-per-node=A100:1
#SBATCH --mem=128G
#SBATCH -t 12:00:00
#SBATCH -o logs/train_%j.out
#SBATCH -e logs/train_%j.err

module load PDC Python/3.11.3-cpeGNU-23.03 CUDA/12.2.0
source $HOME/envs/p10/bin/activate

cd $HOME/repos/portfolio/p10-model-training

export TILES_DIR=/cfs/klemming/scratch/$USER/p10/data/tiles
export RUNS_DIR=/cfs/klemming/scratch/$USER/p10/runs

python src/train.py --config configs/baseline.yaml \
    --tiles-dir $TILES_DIR \
    --runs-dir $RUNS_DIR
```

Submit: `sbatch jobs/train_single_gpu.job`
Monitor: `squeue -u $USER`

### Multi-GPU training job (4× A100)

```bash
#!/bin/bash
#SBATCH -A <your-project-allocation>
#SBATCH -J p10-train-4gpu
#SBATCH -p gpu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=16
#SBATCH --gpus-per-node=A100:4
#SBATCH --mem=256G
#SBATCH -t 06:00:00
#SBATCH -o logs/train_%j.out
#SBATCH -e logs/train_%j.err

module load PDC Python/3.11.3-cpeGNU-23.03 CUDA/12.2.0
source $HOME/envs/p10/bin/activate

cd $HOME/repos/portfolio/p10-model-training

export TILES_DIR=/cfs/klemming/scratch/$USER/p10/data/tiles
export RUNS_DIR=/cfs/klemming/scratch/$USER/p10/runs

accelerate launch \
    --num_processes=4 \
    --mixed_precision=fp16 \
    src/train.py --config configs/baseline.yaml \
        --tiles-dir $TILES_DIR \
        --runs-dir $RUNS_DIR
```

Multi-GPU training reduces wall time by ~3.5× (not 4× due to communication
overhead). Use for foundation model runs (UNI, CONCH) where the A100 memory
is the bottleneck.

### Data pipeline job (tiling on cluster)

```bash
#!/bin/bash
#SBATCH -A <your-project-allocation>
#SBATCH -J p10-tile
#SBATCH -p main
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH -t 08:00:00
#SBATCH -o logs/tile_%j.out
#SBATCH -e logs/tile_%j.err

module load PDC Python/3.11.3-cpeGNU-23.03
source $HOME/envs/p10/bin/activate

cd $HOME/repos/portfolio/p10-model-training

python data/pipeline.py \
    --config configs/baseline.yaml \
    --metadata data/raw/metadata.csv
```

Tiling 587 slides at 512×512 patches takes 2–4 hours on a CPU node with 32
cores. TIAToolbox's WSIReader is not parallelised in `data/tile.py` — tiling
runs sequentially per WSI. To parallelise, wrap the loop in `concurrent.futures`
or submit a separate job per WSI as a SLURM array.

---

## DataLoader tuning on Lustre

Lustre (Dardel's parallel filesystem) performs well with many concurrent reads.
Use `num_workers=16` or more for the DataLoader — each worker reads PNG tiles
independently and Lustre can serve them in parallel:

```python
DataLoader(dataset, batch_size=16, num_workers=16, pin_memory=True, persistent_workers=True)
```

`persistent_workers=True` avoids the overhead of spawning new worker processes
each epoch. `pin_memory=True` speeds up host-to-GPU transfers.

If you see DataLoader becoming the training bottleneck (GPU utilisation < 80%),
increase `num_workers` further or pre-load tiles into a RAM disk:
```bash
# Copy tiles to node-local SSD (available on Dardel GPU nodes)
rsync -a $TILES_DIR/ $LOCAL_SCRATCH/tiles/
```
Then point `tiles_dir` at `$LOCAL_SCRATCH/tiles/` in the job script.

---

## Monitoring a running job

```bash
# Job queue
squeue -u $USER

# Live output
tail -f logs/train_<jobid>.out

# GPU utilisation (on the compute node)
srun --jobid=<jobid> --pty nvidia-smi

# Cancel a job
scancel <jobid>
```

---

## Checkpoints and result retrieval

Checkpoints are written to `$RUNS_DIR/<run_id>/`. After training:

```bash
# Copy best checkpoint back to local machine
rsync -avh \
  <username>@dardel.pdc.kth.se:/cfs/klemming/scratch/<username>/p10/runs/<run_id>/best.pt \
  runs/<run_id>/best.pt

# Copy full metrics log
rsync -avh \
  <username>@dardel.pdc.kth.se:/cfs/klemming/scratch/<username>/p10/runs/<run_id>/metrics.json \
  runs/<run_id>/metrics.json
```

Log the checkpoint to p8 registry after retrieval:
```bash
python -c "
from p8_client import registry  # adjust import for p8's registry interface
registry.log_run(checkpoint='runs/<run_id>/best.pt', metrics='runs/<run_id>/metrics.json')
"
```

---

## Common problems

**ModuleNotFoundError on compute node:**
The compute node environment differs from the login node. Ensure all
`module load` commands are in the job script, not just in your `.bashrc`.

**OOM on A100 (40 GB):**
Reduce `batch_size` from 16 to 8. For UNI/CONCH encoders, also enable gradient
checkpointing in `configs/baseline.yaml` (`gradient_checkpointing: true`).
ViT-L uses ~30 GB at batch size 8 with fp16 — this is close to the A100 limit.

**Lustre quota exceeded:**
Check usage: `lfs quota -u $USER /cfs/klemming`
Delete raw WSIs once tiling is confirmed: `rm -rf $SCRATCH/p10/data/raw/wsis/`
The raw WSIs can be re-downloaded from Grand Challenge if needed.

**Job pending for hours:**
The GPU partition on Dardel can have queues. Check partition status:
`sinfo -p gpu`
If no GPU nodes are available, the job waits. This is expected during peak usage.
Submit during off-peak hours (evenings, weekends) for faster scheduling.

**Scratch data purged:**
Dardel's NOBACKUP scratch purges files not accessed in 30 days. Keep important
outputs (best checkpoints, metrics.json, manifest.csv) in `$HOME` or transfer
to local machine.
