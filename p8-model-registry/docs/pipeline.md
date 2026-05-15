# Benchmark Pipeline Design
*p8 — Model Registry*

---

## What the pipeline does

When a model registry entry changes, the pipeline automatically benchmarks the
model on `quick-thrush` (the actual serving node) and commits the results to git.

```
Model entry updated in registry/models/
        │
        ▼
CI (GitHub Actions) — p8-run-benchmark.yml
  Commits Job manifest to cluster/manifests/
        │
        ▼
ArgoCD detects manifest change
  Applies K8s Job to quick-thrush
        │
        ▼
Job runs on quick-thrush:
  - Clones repo via SSH deploy key
  - Runs PyTorch vs ONNX benchmark
  - Commits results to benchmarks/
  - Pushes back to main
        │
        ▼
benchmarks/<model>-<version>-<date>.yaml in git
```

---

## Why ArgoCD instead of kubectl from CI

The naive approach is for CI to run `kubectl apply` directly. This requires
cluster credentials in GitHub Secrets — a full kubeconfig or service account
token that can connect to the cluster API server.

Our cluster is on a private Tailscale network (`100.123.23.6`). GitHub Actions
runners cannot reach it without adding them to the Tailscale network. Adding
external CI runners to the internal network is a security concern — it expands
the attack surface on the cluster.

ArgoCD already watches the git repository as part of the GitOps setup. By
committing the Job manifest to git, CI delegates cluster interaction entirely
to ArgoCD — which already has cluster access. No credentials leave the cluster.

```
Without ArgoCD:              With ArgoCD:
CI → [credentials] → K8s    CI → git → ArgoCD → K8s
  (CI needs cluster access)   (only ArgoCD needs cluster access)
```

---

## Why the Job writes results back to git

The alternative is for CI to wait for the Job to complete and fetch the logs.
This requires CI to poll the cluster — which again needs cluster credentials.

Instead the Job itself pushes results back:
- Clones the repo using an SSH deploy key mounted as a Kubernetes secret
- Runs the benchmark
- Commits and pushes the result YAML to `benchmarks/`

CI fires and forgets. No polling, no cluster credentials in CI.

---

## Why two workflows — build and run

A single workflow that always builds the image before running the benchmark
would rebuild on every model registry change — even when nothing in the
benchmark code changed. Building a Docker image with PyTorch takes ~5 minutes.

Split into two:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `p8-build-benchmark-image.yml` | `Dockerfile` or `requirements.txt` changed | Builds and pushes `ghcr.io/ahembal/p8-benchmark:latest` |
| `p8-run-benchmark.yml` | Model registry entry changed, or manual | Commits Job manifest — ArgoCD applies it |

The run workflow always uses `:latest` from GHCR. It assumes the image is
already there — built once, reused many times.

---

## Deploy key design

The benchmark Job needs write access to the git repository to push results.
Two deploy keys exist:

| Key | Secret | Purpose |
|-----|--------|---------|
| `argocd-image-updater-ssh-key` | K8s secret in `argocd` | ArgoCD Image Updater writes image tags |
| `p8-benchmark-ssh-key` | K8s secret in `default` | Benchmark Job writes results |

Separate keys follow the principle of least privilege — each key has write
access but is scoped to its specific use. Revoking one does not affect the other.

Both private keys live only as Kubernetes secrets — never in git, never in
GitHub Actions secrets.

---

## How to trigger manually

```bash
gh workflow run p8-run-benchmark.yml \
  --repo ahembal/portfolio \
  -f model_id=resnet18-tiatoolbox-pcam \
  -f version=v1
```

Results appear in `p8-model-registry/benchmarks/` after the Job completes
(typically 3–5 minutes).

---

## Known limitations

- **One job at a time** — if two benchmarks run simultaneously on quick-thrush,
  resource contention will skew latency measurements. The Job requests 2 CPU
  cores but does not prevent other workloads from running on the node.

- **Results depend on node load** — p99 latency is sensitive to other workloads
  on quick-thrush. Numbers from a loaded node are not directly comparable to
  numbers from an idle node. The hardware field in the result records the pod
  name, not load at time of measurement.

- **No automatic cleanup** — committed Job manifests in `cluster/manifests/`
  accumulate over time. Old jobs should be deleted manually or via a cleanup
  script.
