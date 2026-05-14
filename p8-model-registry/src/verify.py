"""
Verify model weights integrity — the trust anchor.

Downloads the weights file from its registered location and computes SHA-256.
Compares against the sha field in the registry entry.

If sha is UNVERIFIED, computes and prints the hash so it can be filled in.

Usage:
  python src/verify.py resnet18-tiatoolbox-pcam v1    # verify specific model
  python src/verify.py --all                           # verify all models
  python src/verify.py --compute resnet18-tiatoolbox-pcam v1  # compute sha to fill in
"""

import hashlib
import sys
import tempfile
from pathlib import Path

import yaml

REGISTRY = Path(__file__).parent.parent / "registry" / "models"


def _sha256(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_huggingface_commit(hub_id: str) -> str:
    """
    Get the current commit hash for a HuggingFace model repo.

    HuggingFace uses commit hashes as canonical version identifiers.
    This is the platform's own integrity mechanism — more reliable than
    computing our own SHA-256 of a downloaded file.
    """
    from huggingface_hub import model_info
    info = model_info(hub_id)
    return info.sha


def _download_rgw(location: str, dest: Path) -> Path:
    """Download model weights from Ceph RGW."""
    import os
    import boto3
    from botocore.client import Config

    # location format: s3://bucket/path/to/file
    parts = location.replace("s3://", "").split("/", 1)
    bucket, key = parts[0], parts[1]
    filename = Path(key).name
    dest_path = dest / filename

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["RGW_ENDPOINT"],
        aws_access_key_id=os.environ["RGW_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RGW_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
    )
    s3.download_file(bucket, key, str(dest_path))
    return dest_path


def verify_model(model_id: str, version: str, compute_only: bool = False) -> bool:
    """
    Verify or compute the SHA for a model entry.

    Args:
        model_id:     model id from registry
        version:      version string e.g. "v1"
        compute_only: if True, just print the SHA without comparing

    Returns:
        True if verified (or compute_only), False if mismatch or error
    """
    yaml_path = REGISTRY / f"{model_id}-{version}.yaml"
    if not yaml_path.exists():
        print(f"ERROR: {yaml_path} not found")
        return False

    with open(yaml_path) as f:
        entry = yaml.safe_load(f)

    registered_sha = entry.get("sha", "UNVERIFIED")
    origin = entry.get("origin", {})
    origin_type = origin.get("type")

    print(f"Verifying {model_id} {version} from {origin_type}...")

    try:
        if origin_type == "huggingface":
            actual_sha = _get_huggingface_commit(origin["hub_id"])
            print(f"HuggingFace commit hash: {actual_sha}")
        elif origin_type == "rgw":
            with tempfile.TemporaryDirectory() as tmp:
                weights_path = _download_rgw(origin["location"], Path(tmp))
                actual_sha = _sha256(weights_path)
                print(f"Computed SHA-256: {actual_sha}")
        else:
            print(f"ERROR: unsupported origin type '{origin_type}'")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

    if compute_only or registered_sha == "UNVERIFIED":
        print(f"\nTo register this, update {yaml_path.name}:")
        print(f"  sha: {actual_sha}")
        return True

    if actual_sha == registered_sha:
        print(f"✓ Verified — matches registry entry")
        return True
    else:
        print(f"✗ MISMATCH")
        print(f"  Registered: {registered_sha}")
        print(f"  Actual:     {actual_sha}")
        print(f"  Do not deploy until this is resolved.")
        return False


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--all" in args:
        results = []
        for yaml_file in REGISTRY.glob("*.yaml"):
            entry = yaml.safe_load(open(yaml_file))
            ok = verify_model(entry["id"], entry["version"])
            results.append(ok)
        sys.exit(0 if all(results) else 1)

    compute_only = "--compute" in args
    if compute_only:
        args = [a for a in args if a != "--compute"]

    if len(args) < 2:
        print("Usage: verify.py [--compute] <model_id> <version>")
        sys.exit(1)

    ok = verify_model(args[0], args[1], compute_only=compute_only)
    sys.exit(0 if ok else 1)
