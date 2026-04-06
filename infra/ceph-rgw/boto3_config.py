"""
infra/ceph-rgw/boto3_config.py
--------------------------------
S3-compatible client factory for Ceph RADOS Gateway (RGW).

Design principles applied here:

1. DEPENDENCY INJECTION
   The factory functions accept an optional `config` parameter rather than
   reading environment variables internally. This means callers can supply
   any RGWConfig — real credentials in production, a mock or localstack
   config in tests — without patching globals or monkeypatching os.environ.
   The module does not decide where config comes from; the caller does.

2. NO LEAKY ABSTRACTION
   Callers receive a plain boto3 client/resource. We do not wrap it in a
   custom class that partially hides the boto3 API — that would force callers
   to learn two APIs and break whenever the wrapper is incomplete. Instead,
   this module's job is solely to construct a correctly configured client
   and hand it over. Storage logic lives elsewhere (see storage/s3.py).

3. FAIL FAST
   Missing credentials raise immediately at construction time with a clear
   message, not later with a cryptic boto3 AuthError mid-operation.

4. SINGLE RESPONSIBILITY
   This file does one thing: produce configured boto3 clients.
   It does not perform any bucket operations, upload logic, or retry handling.
"""

import os
from dataclasses import dataclass

import boto3
from botocore.client import Config


@dataclass(frozen=True)
class RGWConfig:
    """
    Immutable value object holding all connection parameters for a Ceph RGW
    endpoint. Using a dataclass instead of loose keyword arguments makes the
    configuration explicit, type-checkable, and easy to construct in tests.

    frozen=True prevents accidental mutation after construction.
    """

    endpoint: str
    access_key: str
    secret_key: str
    region: str = "default"

    def __post_init__(self):
        """Validate required fields immediately on construction (fail fast)."""
        if not self.endpoint:
            raise ValueError("RGWConfig.endpoint must not be empty")
        if not self.access_key:
            raise ValueError("RGWConfig.access_key must not be empty")
        if not self.secret_key:
            raise ValueError("RGWConfig.secret_key must not be empty")


def config_from_env() -> RGWConfig:
    """
    Construct an RGWConfig from environment variables.

    This is the only place in the codebase that reads os.environ for RGW
    credentials. All other code receives an RGWConfig via dependency injection,
    making it straightforward to test without setting real environment variables.

    Required environment variables:
        RGW_ACCESS_KEY  — S3 access key for the Ceph RGW user
        RGW_SECRET_KEY  — S3 secret key for the Ceph RGW user

    Optional environment variables:
        RGW_ENDPOINT    — RGW base URL (default: http://192.168.1.16)
        RGW_REGION      — region name (default: default)

    Returns:
        RGWConfig: validated configuration object

    Raises:
        ValueError: if RGW_ACCESS_KEY or RGW_SECRET_KEY are missing
    """
    access_key = os.environ.get("RGW_ACCESS_KEY", "")
    secret_key = os.environ.get("RGW_SECRET_KEY", "")

    if not access_key or not secret_key:
        raise ValueError(
            "Environment variables RGW_ACCESS_KEY and RGW_SECRET_KEY must be set. "
            "For local development, export them from your .env file:\n"
            "  export $(cat .env | xargs)"
        )

    return RGWConfig(
        endpoint=os.environ.get("RGW_ENDPOINT", "http://192.168.1.16"),
        access_key=access_key,
        secret_key=secret_key,
        region=os.environ.get("RGW_REGION", "default"),
    )


def get_s3_client(config: RGWConfig):
    """
    Construct a boto3 S3 client configured for Ceph RGW.

    Why not wrap boto3 in a custom class?
    Wrapping boto3 would create a leaky abstraction: any method we don't
    explicitly proxy becomes unavailable, and callers would need to know
    both the wrapper API and when to fall back to the underlying client.
    Instead, we return the raw boto3 client — the abstraction boundary is
    at construction, not at usage.

    Args:
        config: RGWConfig instance (injected by caller)

    Returns:
        boto3.client: configured S3 client ready for use
    """
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name=config.region,
        config=Config(signature_version="s3v4"),
    )


def get_s3_resource(config: RGWConfig):
    """
    Construct a boto3 S3 resource configured for Ceph RGW.

    The resource interface is more object-oriented than the client interface
    (e.g. bucket.objects.all() vs client.list_objects_v2()). Use the resource
    when iterating collections; use the client for fine-grained control and
    presigned URLs.

    Args:
        config: RGWConfig instance (injected by caller)

    Returns:
        boto3.resource: configured S3 resource ready for use
    """
    return boto3.resource(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name=config.region,
        config=Config(signature_version="s3v4"),
    )


if __name__ == "__main__":
    # config_from_env() is called here — at the entry point — not inside the
    # factory functions. This keeps the factories pure and testable while still
    # providing a convenient CLI smoke test.
    cfg = config_from_env()
    client = get_s3_client(cfg)

    print(f"Connected to RGW at {cfg.endpoint}")
    print("Listing buckets...")

    response = client.list_buckets()
    buckets = response.get("Buckets", [])
    if buckets:
        for b in buckets:
            print(f"  {b['Name']}")
    else:
        print("  No buckets yet — connection works.")
