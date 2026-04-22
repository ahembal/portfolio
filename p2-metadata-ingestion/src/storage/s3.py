"""
p2-metadata-ingestion/src/storage/s3.py
-----------------------------------------
S3/RGW storage operations for the metadata ingestion service.

Wraps the boto3 client from infra/ceph-rgw/boto3_config.py with the specific
operations this service needs: upload a file bytes object, check bucket exists,
and build a deterministic S3 key from the job ID.

The key schema is:  uploads/{yyyy}/{mm}/{dd}/{job_id}/{filename}
This partitioning mirrors common data lake conventions and keeps related files
co-located in time — useful for lifecycle policies and batch processing later.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.client import Config


@dataclass(frozen=True)
class RGWConfig:
    endpoint: str
    access_key: str
    secret_key: str
    region: str = "default"

    def __post_init__(self):
        if not self.endpoint:
            raise ValueError("RGWConfig.endpoint must not be empty")
        if not self.access_key:
            raise ValueError("RGWConfig.access_key must not be empty")
        if not self.secret_key:
            raise ValueError("RGWConfig.secret_key must not be empty")


def get_s3_client(config: RGWConfig):
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name=config.region,
        config=Config(signature_version="s3v4"),
    )


def build_s3_key(job_id: str, filename: str) -> str:
    now = datetime.now(tz=timezone.utc)
    safe_filename = Path(filename).name  # strip any path traversal
    return f"uploads/{now:%Y/%m/%d}/{job_id}/{safe_filename}"


def upload_bytes(
    s3_client,
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload raw bytes to the given bucket/key. Raises on any S3 error."""
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def ensure_bucket(s3_client, bucket: str) -> None:
    """Create the bucket if it does not already exist."""
    existing = {b["Name"] for b in s3_client.list_buckets().get("Buckets", [])}
    if bucket not in existing:
        s3_client.create_bucket(Bucket=bucket)


def get_storage_config() -> dict:
    """Read storage config from environment. Raises if credentials are missing."""
    missing = [v for v in ("RGW_ACCESS_KEY", "RGW_SECRET_KEY") if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {missing}")
    return {
        "endpoint": os.environ.get("RGW_ENDPOINT", "http://192.168.1.16"),
        "access_key": os.environ["RGW_ACCESS_KEY"],
        "secret_key": os.environ["RGW_SECRET_KEY"],
        "bucket": os.environ.get("STORAGE_BUCKET", "metadata-files"),
    }
