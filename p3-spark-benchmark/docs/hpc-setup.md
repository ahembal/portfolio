# HPC Setup and Job Submission

Cluster-specific details (usernames, paths, account IDs, storage usage)
are in `docs/hpc-accounts.md.local` — gitignored, never committed.

---

## Clusters overview

| Cluster | System | Use case | Access | Storage |
|---------|--------|----------|--------|---------|
| Dardel | PDC/KTH | GPU + CPU benchmarks | SSH key via PDC portal | Klemming |
| Pelle | UPPMAX/Uppsala | CPU/Spark benchmarks | SUNET required + TOTP | Crex |

---

## Dardel (PDC, KTH)

**Current status:** Active — used for GPU and CPU benchmarks.

### SSH access
```bash
ssh -i ~/.ssh/id_ed25519 <username>@dardel.pdc.kth.se
```

Key must be registered at: `https://loginportal.pdc.kth.se`
- Log in with your SUPR/university account
- Add SSH public key under "Nyckelhantering" (Key management)
- Key is active immediately

No VPN or university network required — accessible from anywhere.

### Partitions
```bash
sinfo                     # list all partitions
sinfo -p gpu              # GPU nodes (AMD MI250X)
sinfo -p main             # CPU nodes (128 cores, 256 GB RAM)
```

### Storage
Klemming filesystem — path in `hpc-accounts.md.local`.
Check usage: `lfs quota -h -u $USER /cfs/klemming`

---

## UPPMAX Pelle

**Current status:** Not yet set up — requires SUNET access.

### SSH access
```bash
ssh <username>@pelle.uppmax.uu.se
```

**Requirements:**
1. **SUNET** — must be on Swedish university network (eduroam, VPN, or on-campus)
   - VPN: `https://www.uppmax.uu.se/support/user-guides/vpn-for-uppmax/`
   - Or use eduroam at any Swedish university
2. **TOTP** — two-factor authentication required
   - Set up via SUPR: `https://supr.naiss.se` → your profile → Two-factor auth
3. **SSH key** — register at SUPR under your account → SSH keys

### Storage
Crex filesystem at `/proj/nbis_support` — 1 TB, ~611 GB free.
Path in `hpc-accounts.md.local`.

### When to use Pelle
- Spark benchmark at large scale (40M+ rows) — more storage headroom than Dardel
- CPU-heavy jobs where Dardel CPU queue is long
- Once SUNET VPN + TOTP is set up, identical workflow to Dardel

---

## General workflow (both clusters)

### First time setup
```bash
# SSH to cluster, go to your project storage directory
cd <your-project-dir>
mkdir -p portfolio/code && cd portfolio/code
git clone git@github.com:ahembal/portfolio.git .
cd p3-spark-benchmark
pip install --user pandas pyarrow requests
```

### Before each run
```bash
git pull   # sync latest code
```

### Data staging
Fetch once — data stays on cluster, reused across runs.
Delete `data/` after runs to free storage (re-fetchable from NCBI in ~30 min).

```bash
python src/fetch_data.py --sample 10M --out <your-project-dir>/p3/data/
python src/fetch_data.py --sample 40M --out <your-project-dir>/p3/data/
```

### Submitting jobs
```bash
# GPU benchmark (Dardel)
export PROJECT=<your-project-dir>
sbatch jobs/dardel_gpu.sh

# Spark benchmark (Dardel CPU or Pelle)
export PROJECT=<your-project-dir>
sbatch jobs/uppmax_spark.sh      # also works on Dardel with -p main

squeue -u $USER                  # monitor
tail -f <job_id>_spark.out       # live log
```

### Retrieving results
```bash
# Copy timing JSONs to local repo
scp <user>@dardel.pdc.kth.se:<your-project-dir>/p3/results/*.json \
    results/

# Consolidate
python -c "
import json, glob, pandas as pd
rows = [json.loads(open(f).read()) for f in glob.glob('results/*.json')]
pd.DataFrame(rows).to_csv('results/benchmark_table.csv', index=False)
print(pd.DataFrame(rows)[['approach','scale','nodes','total_s','throughput_M_rows_per_s']])
"
git add results/ && git commit -m 'feat(p3): add HPC benchmark results'
git push
```
