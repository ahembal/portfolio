# Data Source — NCBI SRA Metadata

## What is SRA?

The Sequence Read Archive (SRA) is NCBI's primary repository for raw sequencing
data. Every sequencing run deposited to NCBI, EBI (via ENA), or DDBJ gets an
SRA accession. As of April 2026 the archive contains ~40 million sequencing runs
totalling several exabytes of data.

For SciLifeLab specifically, SRA metadata is relevant because:
- NBIS/SciLifeLab users deposit data to SRA as part of publication requirements
- The metadata catalog is a real-world large-scale dataset with skewed distributions
  (a few centers dominate, base counts span many orders of magnitude)
- Processing SRA metadata is a realistic data engineering task in genomics

## Source file

```
URL:  https://ftp.ncbi.nlm.nih.gov/sra/reports/Metadata/SRA_Accessions.tab
Type: Tab-separated, updated daily
Size: ~32 GB uncompressed (April 2026)
Rows: ~65M total (all record types); ~40M RUN records
Auth: None required
```

## Schema (columns used in benchmark)

| Column | Type | Description |
|--------|------|-------------|
| Accession | str | SRA accession (SRR/ERR/DRR prefix) |
| Status | category | `live` / `suppressed` / `unpublished` |
| Published | datetime | Date first publicly available |
| Center | category | Submitting center (e.g. GEO, BROAD, BGI) |
| Spots | int | Number of reads in the run |
| Bases | int | Total base count — primary measure of run size |
| BioProject | str | Parent project accession |

We filter to `Type=RUN` and `Status=live` — the active sequencing runs.

## Fetch performance (observed 2026-04-29)

Streaming via HTTPS from NCBI FTP:

| Scale | RUN records | Transfer size | Wall time | Throughput |
|-------|-------------|--------------|-----------|------------|
| 1M    | 1,000,000   | ~0.17 GB     | 192 s     | ~0.9 MB/s  |
| 10M   | 10,000,000  | ~1.7 GB      | ~32 min (est.) | ~0.9 MB/s |
| 40M   | 40,000,000  | ~6.8 GB      | ~2.1 h (est.) | ~0.9 MB/s |

**NCBI rate-limits unauthenticated FTP connections to ~1 MB/s.**
For the 10M and 40M datasets, fetch directly on HPC where the data can also
be pre-staged once and reused across all benchmark runs.

## How to fetch

```bash
# 1M locally (for pandas baseline, ~3 min)
python src/fetch_data.py --sample 1M --out data/

# 10M or 40M — run on HPC to avoid laptop bandwidth limits
python src/fetch_data.py --sample 10M --out /proj/nbis_support/portfolio/p3/data/
python src/fetch_data.py --sample 40M --out /proj/nbis_support/portfolio/p3/data/
```

The script streams the file line-by-line, filters to `Type=RUN`, and writes
Parquet partitioned by nothing (single file per scale). A `platform_lookup.parquet`
file (10 rows, used for the broadcast join step) is always written alongside.

## Data validity notes

- ~3–5% of RUN records have `Bases=0` or `NULL` — these are filtered out in
  the pipeline (likely suppressed or in-progress submissions)
- `Published` timestamps have sparse coverage before 2010 — the archive began
  accepting submissions in 2007 but backfilling was gradual
- `Center` values are not standardised — "ILLUMINA", "Illumina", "illumina"
  all appear. The platform_lookup only covers the top-10 submitters; the rest
  map to `technology=NULL` and are excluded from the window step
