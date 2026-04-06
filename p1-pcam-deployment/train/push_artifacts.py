"""
p1-pcam-deployment/train/push_artifacts.py
--------------------------------------------
Transfers training artifacts from Crex (UPPMAX) to Ceph RGW on turtle.

This script runs at the end of the SLURM job, bridging the HPC environment
(where the model was trained) and the homelab (where it will be served).

Design principles:

1. SINGLE RESPONSIBILITY
   This script does one thing: move files from a local directory to S3.
   It does not know anything about training or model formats.

2. DEPENDENCY INJECTION
   RGWConfig is constructed from environment variables at the entry point
   (main()), not inside the upload functions. The upload function receives
   a pre-built s3 client — making it testable without a real RGW endpoint.

3. FAIL FAST
   The script checks that the source directory exists and contains expected
   artifacts before attempting any upload. A missing checkpoint raises
   immediately rather than silently uploading an empty directory.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "ceph-rgw"))
from boto3_config import RGWConfig, get_s3_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

EXPECTED_ARTIFACTS = ["best_model.pt", "metrics.json", "config.json"]


def validate_source(source_dir: Path) -> None:
    """
    Check that the source directory exists and contains expected artifacts.

    Args:
        source_dir: path to the training output directory

    Raises:
        FileNotFoundError: if directory or a required artifact is missing
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    for artifact in EXPECTED_ARTIFACTS:
        path = source_dir / artifact
        if not path.exists():
            raise FileNotFoundError(
                f"Expected artifact missing: {path}\n"
                f"Did the training job complete successfully?"
            )


def upload_directory(s3_client, source_dir: Path, bucket: str, prefix: str) -> list:
    """
    Upload all files in source_dir to s3://bucket/prefix/.

    Args:
        s3_client:  boto3 S3 client (injected)
        source_dir: local directory to upload
        bucket:     S3 bucket name
        prefix:     S3 key prefix (e.g. pcam/12345678)

    Returns:
        list of uploaded S3 keys
    """
    uploaded = []

    for file_path in sorted(source_dir.iterdir()):
        if not file_path.is_file():
            continue

        s3_key = f"{prefix}/{file_path.name}"
        log.info(f"Uploading {file_path.name} → s3://{bucket}/{s3_key}")

        s3_client.upload_file(
            Filename=str(file_path),
            Bucket=bucket,
            Key=s3_key,
        )
        uploaded.append(s3_key)

    return uploaded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push training artifacts from Crex to Ceph RGW"
    )
    parser.add_argument("--source-dir", required=True, help="Local artifact directory")
    parser.add_argument("--bucket",     required=True, help="S3 bucket name")
    parser.add_argument("--prefix",     required=True, help="S3 key prefix")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    validate_source(source_dir)

    # Construct RGWConfig from environment — only at the entry point
    cfg = RGWConfig(
        endpoint=os.environ.get("RGW_ENDPOINT", "http://192.168.1.16"),
        access_key=os.environ["RGW_ACCESS_KEY"],
        secret_key=os.environ["RGW_SECRET_KEY"],
    )
    s3 = get_s3_client(cfg)

    uploaded = upload_directory(s3, source_dir, args.bucket, args.prefix)

    log.info(f"Uploaded {len(uploaded)} files to s3://{args.bucket}/{args.prefix}/")
    for key in uploaded:
        log.info(f"  s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()
