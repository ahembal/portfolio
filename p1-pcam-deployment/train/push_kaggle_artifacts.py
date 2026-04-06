"""
p1-pcam-deployment/train/push_kaggle_artifacts.py
---------------------------------------------------
Pushes artifacts downloaded from a Kaggle run to Ceph RGW on turtle.

Workflow:
  1. Run kaggle_train.ipynb on Kaggle (T4 GPU)
  2. Download output zip from Kaggle → ~/Downloads/
  3. Run this script:
       python push_kaggle_artifacts.py --zip ~/Downloads/output.zip --run-id kaggle-001

This is the manual bridge between Kaggle compute and turtle storage.
Later this step will be replaced by push_artifacts.py running directly
on Dardel (which is on the same network as turtle via VPN or direct SSH).

Design principles:
  SINGLE RESPONSIBILITY — this script only extracts and uploads, nothing else.
  DEPENDENCY INJECTION  — receives RGWConfig from environment, s3 client injected.
  FAIL FAST             — validates zip contents before any upload attempt.
"""

import argparse
import logging
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "ceph-rgw"))
from boto3_config import RGWConfig, get_s3_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

EXPECTED_ARTIFACTS = ["best_model.pt", "metrics.json", "config.json"]


def extract_zip(zip_path: Path, extract_to: Path) -> Path:
    """
    Extract Kaggle output zip to a temp directory.

    Kaggle output zips contain a flat structure or a single subdirectory.
    We find the checkpoints/ folder wherever it lives inside the zip.

    Args:
        zip_path:   path to downloaded Kaggle zip
        extract_to: directory to extract into

    Returns:
        Path to the extracted checkpoints directory

    Raises:
        FileNotFoundError: if zip doesn't contain expected artifacts
    """
    log.info(f"Extracting {zip_path} → {extract_to}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    # Find checkpoints dir — may be nested
    candidates = list(extract_to.rglob("best_model.pt"))
    if not candidates:
        raise FileNotFoundError(
            f"best_model.pt not found inside {zip_path}. "
            f"Contents: {list(extract_to.rglob('*'))}"
        )
    return candidates[0].parent


def validate_artifacts(artifact_dir: Path) -> None:
    """Check all expected artifacts are present before uploading."""
    for name in EXPECTED_ARTIFACTS:
        path = artifact_dir / name
        if not path.exists():
            raise FileNotFoundError(
                f"Expected artifact missing: {path}"
            )
    log.info("All expected artifacts present — proceeding with upload")


def upload_artifacts(s3_client, artifact_dir: Path, bucket: str, prefix: str) -> list:
    """
    Upload all files in artifact_dir to s3://bucket/prefix/.

    Args:
        s3_client:    boto3 S3 client (injected)
        artifact_dir: local directory containing artifacts
        bucket:       S3 bucket name
        prefix:       S3 key prefix (e.g. pcam/kaggle-001)

    Returns:
        list of uploaded S3 keys
    """
    uploaded = []
    for file_path in sorted(artifact_dir.iterdir()):
        if not file_path.is_file():
            continue
        s3_key = f"{prefix}/{file_path.name}"
        size_mb = file_path.stat().st_size / 1024 / 1024
        log.info(f"Uploading {file_path.name} ({size_mb:.1f} MB) → s3://{bucket}/{s3_key}")
        s3_client.upload_file(
            Filename=str(file_path),
            Bucket=bucket,
            Key=s3_key,
        )
        uploaded.append(s3_key)
    return uploaded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push Kaggle output artifacts to Ceph RGW"
    )
    parser.add_argument(
        "--zip", required=True,
        help="Path to downloaded Kaggle output zip"
    )
    parser.add_argument(
        "--run-id", required=True,
        help="Unique run identifier used as S3 prefix (e.g. kaggle-001)"
    )
    parser.add_argument(
        "--bucket", default="ml-artifacts",
        help="S3 bucket name (default: ml-artifacts)"
    )
    args = parser.parse_args()

    zip_path   = Path(args.zip).expanduser().resolve()
    extract_to = zip_path.parent / f"extracted_{args.run_id}"
    extract_to.mkdir(exist_ok=True)

    artifact_dir = extract_zip(zip_path, extract_to)
    validate_artifacts(artifact_dir)

    cfg = RGWConfig(
        endpoint=os.environ.get("RGW_ENDPOINT", "http://192.168.1.16"),
        access_key=os.environ["RGW_ACCESS_KEY"],
        secret_key=os.environ["RGW_SECRET_KEY"],
    )
    s3 = get_s3_client(cfg)

    prefix   = f"pcam/{args.run_id}"
    uploaded = upload_artifacts(s3, artifact_dir, args.bucket, prefix)

    log.info(f"Done — {len(uploaded)} files at s3://{args.bucket}/{prefix}/")
    for key in uploaded:
        log.info(f"  s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()
