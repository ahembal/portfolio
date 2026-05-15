#!/bin/sh
set -e

MODEL_ID=$1
VERSION=$2

if [ -z "$MODEL_ID" ] || [ -z "$VERSION" ]; then
    echo "Usage: $0 <model_id> <version>"
    exit 1
fi

# Configure SSH with deploy key mounted as a secret
mkdir -p ~/.ssh
cp /secrets/ssh-key ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519
ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null

# Configure git identity
git config --global user.name  "p8-benchmark[bot]"
git config --global user.email "p8-benchmark[bot]@users.noreply.github.com"

# Clone repo
git clone git@github.com:ahembal/portfolio.git /repo
cd /repo/p8-model-registry

# Run benchmark
PYTHONPATH=. python src/benchmark.py "$MODEL_ID" "$VERSION"

# Commit and push results
RESULT=$(ls benchmarks/${MODEL_ID}-${VERSION}-*.yaml | tail -1)
if [ -z "$RESULT" ]; then
    echo "ERROR: no benchmark result file found"
    exit 1
fi

git add "$RESULT"
git diff --staged --quiet && echo "No changes to commit" && exit 0

git commit -m "ci(p8): benchmark ${MODEL_ID} ${VERSION} on $(hostname)"
git pull --rebase
git push

echo "Results committed: $RESULT"
