"""
p12 — Feature store loader.

Writes transformed records to the Parquet feature store on Ceph RGW.
Partitioned by year and month so consumers can read only what they need.
Append-only — existing partitions are never overwritten.

Feature store layout:
    s3://pipeline-features/pubmed/year=YYYY/month=MM/part-{run_date}.parquet
"""

import logging
import os
from datetime import date

import boto3
import pandas as pd
from botocore.client import Config
from io import BytesIO

log = logging.getLogger("p12.load")

BUCKET  = os.getenv("FEATURE_STORE_BUCKET", "pipeline-features")
PREFIX  = "pubmed"


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["RGW_ENDPOINT"],
        aws_access_key_id=os.environ["RGW_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RGW_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
    )


def write(records: list[dict], run_date: date | None = None) -> dict[str, int]:
    """
    Write records to the feature store, partitioned by year and month.

    Records without a parseable pubdate are written to year=unknown/month=unknown.

    Returns a dict mapping partition key → row count written.
    """
    if run_date is None:
        run_date = date.today()

    s3 = _s3_client()
    df = pd.DataFrame(records)
    df["_run_date"] = run_date.isoformat()

    counts: dict[str, int] = {}

    for (year, month), group in _partition(df):
        key = f"{PREFIX}/year={year}/month={month:02d}/part-{run_date.isoformat()}.parquet"
        buf = BytesIO()
        group.to_parquet(buf, index=False, engine="pyarrow")
        buf.seek(0)
        s3.put_object(Bucket=BUCKET, Key=key, Body=buf.read())
        log.info("partition_written", extra={"key": key, "rows": len(group)})
        counts[f"year={year}/month={month:02d}"] = len(group)

    return counts


def _partition(df: pd.DataFrame):
    """Yield (year, month), group_df for each partition."""
    import re

    def parse_year_month(pubdate: str):
        m = re.search(r"(\d{4})", str(pubdate))
        year = int(m.group(1)) if m else 0
        m2 = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", str(pubdate))
        month_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                     "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
        month = month_map.get(m2.group(1), 1) if m2 else 1
        return year, month

    df[["_year","_month"]] = pd.DataFrame(
        df["pubdate"].apply(parse_year_month).tolist(), index=df.index
    )
    for (year, month), group in df.groupby(["_year","_month"]):
        yield (year, month), group.drop(columns=["_year","_month"])
