"""
p12 — Run lineage recorder.

Writes a JSON record for each pipeline run to the _lineage/ prefix in the
feature store. Each record captures source, extraction date, row counts,
rejection totals, and partition breakdown.

Lineage records are append-only and keyed by run date. They are the audit
trail for the feature store — if a downstream model degrades, lineage records
identify which pipeline run introduced the change.
"""

import json
import logging
import os
from datetime import date

import boto3
from botocore.client import Config

log = logging.getLogger("p12.lineage")

BUCKET = os.getenv("FEATURE_STORE_BUCKET", "pipeline-features")


def record_run(
    run_date: str,
    extracted: int,
    accepted: int,
    rejected: int,
    partitions: dict[str, int],
) -> None:
    """Write a lineage record for one pipeline run."""
    entry = {
        "run_date":        run_date,
        "source":          "pubmed-entrez",
        "extracted":       extracted,
        "accepted":        accepted,
        "rejected":        rejected,
        "acceptance_rate": round(accepted / extracted, 4) if extracted > 0 else 0.0,
        "partitions":      partitions,
    }
    key = f"_lineage/{run_date}.json"
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["RGW_ENDPOINT"],
        aws_access_key_id=os.environ["RGW_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RGW_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
    )
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(entry, indent=2))
    log.info("lineage_recorded", extra={"key": key, "accepted": accepted, "rejected": rejected})
