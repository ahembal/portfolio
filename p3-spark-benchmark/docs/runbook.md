# Runbook — Debugging and Operations

## Running the benchmark

### Local (pandas baseline)
```bash
pip install -r requirements.txt
python src/fetch_data.py --sample 1M --out data/
python src/pipeline_pandas.py --data data/sra_runs_1M.parquet --out results/
```

### UPPMAX (Spark)
```bash
ssh <user>@rackham.uppmax.uu.se
cd /proj/nbis_support/portfolio/code/p3-spark-benchmark
sbatch jobs/uppmax_spark.sh
squeue -u $USER          # monitor
jobinfo <job_id>         # detailed info
```

### Dardel (GPU)
```bash
ssh <user>@dardel.pdc.kth.se
cd /proj/nbis_support/portfolio/code/p3-spark-benchmark
sbatch jobs/dardel_gpu.sh
squeue -u $USER
```

---

## Common issues

### fetch_data.py stalls mid-download

NCBI FTP drops connections after ~100 MB. The script buffers by chunks and
resumes from where the last chunk ended. If it hangs completely:
```bash
# Kill and restart — it will resume from the last saved chunk
# (data is only written at the end, so restart fetches from scratch)
```
For large scales (10M+), fetch on HPC to avoid laptop connectivity issues.

### pipeline_pandas.py — MemoryError

40M rows requires ~12 GB RAM. If the laptop has < 16 GB:
- Use `--sample 10M` for local testing
- Run 40M only on HPC

### Spark job fails: "No space left on device"

Spark writes shuffle spill to `/tmp`. On UPPMAX `/tmp` is node-local and
limited. Add to spark-submit:
```
--conf spark.local.dir=/proj/nbis_support/tmp
```

### Spark job fails: "Connection refused" on port 7077

The Spark master didn't start or the job requested more nodes than available.
Check `%j_spark.err` for the actual error. Common fix: reduce `--nodes` to 1
and test first.

### cuDF ImportError on Dardel

```
ModuleNotFoundError: No module named 'cudf'
```
Module not loaded. Check:
```bash
module list | grep RAPIDS
module load RAPIDS/24.06-rocm-6.0-python-3.11
```
If the module name changed: `module spider RAPIDS` to list available versions.

### cuDF: "GPU out of memory"

Unlikely at 40M rows (15 GB used, 128 GB available). If it occurs, check for
other jobs using the same GPU:
```bash
rocm-smi  # AMD equivalent of nvidia-smi
```

### Results look wrong (output mismatch between pandas and Spark)

Run the diff check:
```bash
python -c "
import pandas as pd
p = pd.read_parquet('results/pandas_sra_runs_10M_result.parquet')
s = pd.read_parquet('results/spark_sra_runs_10M_result.parquet')
p_sorted = p.sort_values(['Center','technology','year']).reset_index(drop=True)
s_sorted = s.sort_values(['Center','technology','year']).reset_index(drop=True)
print(p_sorted[['total_bases','run_count']].equals(s_sorted[['total_bases','run_count']]))
"
```
Common cause: Spark floating-point aggregation differs from pandas for `mean_bases`.
This is expected — `total_bases` and `run_count` (integers) should match exactly.

## Collecting results

After all runs complete, consolidate timing JSONs:
```bash
python -c "
import json, glob, pandas as pd
rows = [json.loads(open(f).read()) for f in glob.glob('results/*.json')]
pd.DataFrame(rows).to_csv('results/benchmark_table.csv', index=False)
print(pd.DataFrame(rows)[['approach','scale','nodes','total_s','throughput_M_rows_per_s']])
"
```
