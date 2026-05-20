#!/bin/sh
set -e

# Configure SSH with deploy key mounted at /secrets/ssh-key
mkdir -p ~/.ssh
cp /secrets/ssh-key ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519
ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null

git config --global user.name  "p9-builder[bot]"
git config --global user.email "p9-builder[bot]@users.noreply.github.com"

git clone git@github.com:ahembal/portfolio.git /repo
cd /repo/p9-knowledge-graph

# Build the graph — fetches from PubMed and UniProt
PYTHONPATH=. python src/builder.py

# Upload graph.ttl to RGW
python3 - <<'EOF'
import boto3, os
from pathlib import Path

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["RGW_ENDPOINT"],
    aws_access_key_id=os.environ["RGW_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RGW_SECRET_KEY"],
)

bucket = os.environ.get("RGW_BUCKET", "p9-graph")
key    = os.environ.get("RGW_KEY",    "graph.ttl")

# Create bucket if it does not exist
existing = [b["Name"] for b in s3.list_buckets()["Buckets"]]
if bucket not in existing:
    s3.create_bucket(Bucket=bucket)

s3.upload_file("data/seed/graph.ttl", bucket, key)
print(f"Uploaded graph.ttl to s3://{bucket}/{key}")
EOF

echo "Graph build complete."
