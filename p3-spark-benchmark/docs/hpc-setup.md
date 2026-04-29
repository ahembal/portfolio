# HPC Setup and Job Submission

## Code deployment

Both UPPMAX and Dardel have access to `/proj/nbis_support/` (Crex storage).
The simplest approach is to clone the portfolio repo directly on the cluster.

### First time setup (run once per cluster)

Allocation details are in `docs/hpc-accounts.md.local` (gitignored).

```bash
# On UPPMAX (Pelle)
ssh <user>@pelle.uppmax.uu.se
cd /proj/nbis_support/portfolio
git clone git@github.com:ahembal/portfolio.git code
cd code/p3-spark-benchmark
pip install --user pandas pyarrow requests

# On Dardel
ssh <user>@dardel.pdc.kth.se
cd /proj/nbis_support/portfolio
git clone git@github.com:ahembal/portfolio.git code
```

### Updating code before a run

```bash
cd /proj/nbis_support/portfolio/code
git pull
```

## Data staging

Fetch data once per cluster — it lives in shared Crex storage, visible from
all compute nodes.

```bash
# On UPPMAX (fetch 10M + 40M — ~2 GB + ~7 GB, takes ~30-40 min each)
python /proj/nbis_support/portfolio/code/p3-spark-benchmark/src/fetch_data.py \
    --sample 10M --out /proj/nbis_support/portfolio/p3/data/

python /proj/nbis_support/portfolio/code/p3-spark-benchmark/src/fetch_data.py \
    --sample 40M --out /proj/nbis_support/portfolio/p3/data/
```

On Dardel the same `/proj/nbis_support/` path is accessible — no need to
fetch again if already staged on UPPMAX.

## Submitting jobs

### UPPMAX — Spark benchmark
```bash
ssh <user>@rackham.uppmax.uu.se
cd /proj/nbis_support/portfolio/code/p3-spark-benchmark
sbatch jobs/uppmax_spark.sh

# Monitor
squeue -u $USER
jobinfo <job_id>

# Output logs
tail -f <job_id>_spark.out
```

### Dardel — GPU benchmark
```bash
ssh <user>@dardel.pdc.kth.se
cd /proj/nbis_support/portfolio/code/p3-spark-benchmark
sbatch jobs/dardel_gpu.sh

# Monitor
squeue -u $USER
tail -f <job_id>_gpu.out
```

## Retrieving results

After jobs complete, results are in `/proj/nbis_support/portfolio/p3/results/`.
Copy them back to the local repo:

```bash
# From your laptop
scp <user>@rackham.uppmax.uu.se:/proj/nbis_support/portfolio/p3/results/*.json \
    /home/emrebalsever/repos/portfolio/p3-spark-benchmark/results/

scp <user>@dardel.pdc.kth.se:/proj/nbis_support/portfolio/p3/results/*.json \
    /home/emrebalsever/repos/portfolio/p3-spark-benchmark/results/
```

Then consolidate and commit:
```bash
cd /home/emrebalsever/repos/portfolio/p3-spark-benchmark
python -c "
import json, glob, pandas as pd
rows = [json.loads(open(f).read()) for f in glob.glob('results/*.json')]
pd.DataFrame(rows).to_csv('results/benchmark_table.csv', index=False)
"
git add results/ && git commit -m 'feat(p3): add HPC benchmark results'
git push
```
