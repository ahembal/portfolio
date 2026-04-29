"""
Download and prepare NCBI SRA metadata for benchmarking.

Source: https://ftp.ncbi.nlm.nih.gov/sra/reports/Metadata/SRA_Accessions.tab
Updated daily. No authentication required.

Usage:
    python src/fetch_data.py --out data/ --sample 10M
    python src/fetch_data.py --out data/ --full        # downloads full ~32 GB

The file is tab-separated with columns:
    Accession, Submission, Status, Updated, Published, Received,
    Type, Center, Visibility, Alias, Experiment, Sample, Study,
    Loaded, Spots, Bases, Md5sum, BioSample, BioProject, ReplacedBy

We filter to Type=RUN (sequencing runs) which gives ~40M rows in the full file.
"""

import argparse
import time
from pathlib import Path

import pandas as pd
import requests

SRA_URL = "https://ftp.ncbi.nlm.nih.gov/sra/reports/Metadata/SRA_Accessions.tab"

# Columns we need — drop the rest to keep memory manageable
USECOLS = ["Accession", "Status", "Updated", "Published", "Type",
           "Center", "Visibility", "Spots", "Bases", "BioProject"]

DTYPES = {
    "Accession":  "str",
    "Status":     "category",
    "Type":       "category",
    "Center":     "category",
    "Visibility": "category",
    "BioProject": "str",
}

# Platform/center lookup — small broadcast table for the join step
PLATFORM_LOOKUP = pd.DataFrame({
    "Center": [
        "NCBI", "EBI", "DDBJ", "GEO", "SRA", "BROAD", "BGI",
        "ILLUMINA", "PACBIO", "OXFORD_NANOPORE",
    ],
    "technology": [
        "short-read", "short-read", "short-read", "microarray", "short-read",
        "short-read", "short-read", "short-read", "long-read", "long-read",
    ],
    "region": [
        "us", "eu", "jp", "us", "us", "us", "cn", "us", "us", "uk",
    ],
})


def fetch_sample(n_rows: int, out_dir: Path) -> None:
    """Stream the first n_rows RUN records without downloading the full file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"sra_runs_{n_rows // 1_000_000}M.parquet"
    lookup_path = out_dir / "platform_lookup.parquet"

    if out_path.exists():
        print(f"Already exists: {out_path}")
    else:
        print(f"Streaming SRA metadata to collect {n_rows:,} RUN records...")
        t0 = time.perf_counter()
        chunks, total = [], 0
        chunk_size = 500_000

        resp = requests.get(SRA_URL, stream=True)
        resp.raise_for_status()

        import io
        header = None
        buffer = ""

        for raw_chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):
            buffer += raw_chunk.decode("utf-8", errors="replace")
            lines = buffer.split("\n")
            buffer = lines[-1]  # keep incomplete last line

            if header is None:
                header = lines[0]
                lines = lines[1:]

            chunk_data = "\n".join([header] + [l for l in lines if l])
            if not chunk_data.strip():
                continue

            df = pd.read_csv(
                io.StringIO(chunk_data), sep="\t",
                usecols=USECOLS, dtype=DTYPES,
                on_bad_lines="skip",
            )
            df = df[df["Type"] == "RUN"].copy()
            df["Spots"] = pd.to_numeric(df["Spots"], errors="coerce")
            df["Bases"] = pd.to_numeric(df["Bases"], errors="coerce")
            df["Published"] = pd.to_datetime(df["Published"], errors="coerce", utc=True)

            chunks.append(df)
            total += len(df)
            print(f"  collected {total:,} RUN records...", end="\r")

            if total >= n_rows:
                break

        resp.close()
        df = pd.concat(chunks, ignore_index=True).head(n_rows)
        df.to_parquet(out_path, index=False)
        print(f"\nSaved {len(df):,} rows → {out_path} ({time.perf_counter()-t0:.1f}s)")

    PLATFORM_LOOKUP.to_parquet(lookup_path, index=False)
    print(f"Lookup table → {lookup_path}")


def fetch_full(out_dir: Path) -> None:
    """Download the full SRA_Accessions.tab and convert to Parquet (~32 GB → ~4 GB)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "SRA_Accessions.tab"
    out_path = out_dir / "sra_runs_full.parquet"

    if not raw_path.exists():
        print("Downloading full SRA_Accessions.tab (~32 GB)...")
        with requests.get(SRA_URL, stream=True) as r:
            r.raise_for_status()
            with open(raw_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=16 * 1024 * 1024):
                    f.write(chunk)

    if not out_path.exists():
        print("Converting to Parquet (RUN records only)...")
        chunks = []
        for chunk in pd.read_csv(raw_path, sep="\t", usecols=USECOLS,
                                  dtype=DTYPES, chunksize=1_000_000):
            runs = chunk[chunk["Type"] == "RUN"]
            chunks.append(runs)
        df = pd.concat(chunks, ignore_index=True)
        df.to_parquet(out_path, index=False)
        print(f"Saved {len(df):,} rows → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data")
    parser.add_argument("--sample", choices=["1M", "10M", "40M"], default="10M")
    parser.add_argument("--full", action="store_true", help="Download full file")
    args = parser.parse_args()

    SAMPLE_SIZES = {"1M": 1_000_000, "10M": 10_000_000, "40M": 40_000_000}

    if args.full:
        fetch_full(Path(args.out))
    else:
        fetch_sample(SAMPLE_SIZES[args.sample], Path(args.out))
