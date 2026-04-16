#!/bin/bash
# Build the PCam inference Docker image.
# Must be run from the repo root so the build context includes infra/.
#
# Usage (from repo root):
#   bash p1-pcam-deployment/serving/build.sh

set -euo pipefail

IMAGE_NAME="pcam-inference"
IMAGE_TAG="${1:-latest}"

echo "Building ${IMAGE_NAME}:${IMAGE_TAG}..."

docker build \
  --file p1-pcam-deployment/serving/Dockerfile \
  --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
  . # build context is repo root — gives access to infra/ceph-rgw/

echo "Done: ${IMAGE_NAME}:${IMAGE_TAG}"
