# Q7 — Docker, Helm, and Kubernetes in Practice

This document walks through the concrete infrastructure decisions made in the
PCam inference service deployment. Every choice below has a corresponding file
in the repository.

---

## 1. Docker — multi-stage distroless image

**File:** `serving/Dockerfile`

### Multi-stage build

```dockerfile
FROM python:3.11-slim AS builder
# pip install into /install — includes build tools, wheel, compilers
RUN pip install --prefix=/install -r requirements.txt

FROM gcr.io/distroless/python3-debian12:nonroot
# Copy only the installed packages — no pip, no compilers
COPY --from=builder /install/lib/python3.11/site-packages ...
```

The builder stage needs pip and compilers to install packages.
The runtime stage gets only the installed packages — no build tooling at all.
Result: the final image contains only what runs at production.

### Why distroless

`python:3.11-slim` ships bash, apt, coreutils, and ~100 other packages the app
never uses. Each is a potential CVE. `gcr.io/distroless/python3-debian12:nonroot`
contains only the Python interpreter and its direct runtime dependencies.
No shell, no package manager, no curl. An attacker with code execution inside
the container has no pivot tools.

Trivy scans show significantly fewer CVEs compared to slim.
Image is ~60 MB smaller.

Compliance: NIST SP 800-190 §4.1, ISO 27001:2022 A.8.8, CIS Docker Benchmark 4.1.

### Non-root UID

Distroless ships with a single non-root user: `nonroot`, UID 65532. The Dockerfile
does not create a user — it uses the one the base image provides.

The Kubernetes deployment mirrors this:
```yaml
securityContext:
  runAsNonRoot: true   # K8s rejects the pod if image runs as UID 0
  runAsUser: 65532
```

CIS Kubernetes Benchmark 5.2.7.

### Model not embedded in image

The model checkpoint (~45 MB) is downloaded from Ceph RGW at container startup
inside FastAPI's `lifespan()` function. The readiness probe only passes after the
model is loaded, so Kubernetes never routes traffic to a pod that hasn't finished
loading. This means:

- The same image works for any model version — just change `MODEL_KEY` in the ConfigMap
- Image rebuilds are triggered only by code changes, not model retraining
- CI/CD and model versioning are decoupled

---

## 2. Helm chart

**Directory:** `helm/pcam-inference/`

### Chart structure

```
Chart.yaml          — name, version, appVersion
values.yaml         — all tunables with defaults
templates/
  _helpers.tpl      — fullname, labels, selectorLabels helpers
  deployment.yaml   — Pod spec, probes, resource limits, env injection
  service.yaml      — ClusterIP on port 80 → 8080
  configmap.yaml    — non-sensitive env vars (RGW endpoint, model key)
  hpa.yaml          — CPU-based autoscaler, min 1 / max 4
  ingress.yaml      — Nginx ingress (gated by ingress.enabled=false)
```

### Parameterisation

`values.yaml` exposes every tunable — image tag, resource requests/limits,
probe delays, HPA thresholds, RGW endpoint — without requiring template edits.
CI updates `image.tag` to the git SHA on every build and commits it back.
ArgoCD detects the change and deploys.

Switching environments (dev vs. prod) requires only a values override file, not
forking the templates.

### HPA and replica conflict

If `hpa.enabled: true`, the chart omits the `replicas:` field from the Deployment:

```yaml
{{- if not .Values.hpa.enabled }}
replicas: {{ .Values.replicaCount }}
{{- end }}
```

Without this guard, `helm upgrade` resets `replicas` to 1 on every deploy,
fighting the HPA. With the guard, the HPA owns the replica count after first deploy.

### Secret injection

Credentials (RGW access/secret key) are injected as individual env vars, not via
`envFrom: secretRef` which would expose all keys in the Secret:

```yaml
env:
  - name: RGW_ACCESS_KEY
    valueFrom:
      secretKeyRef:
        name: {{ .Values.credentialsSecret }}
        key: access-key
```

Explicit mapping makes auditing clear: you can see exactly which keys the pod consumes.
Compliance: ISO 27001:2022 A.8.4.

---

## 3. Kubernetes

**Cluster:** 3-node homelab (1 control plane + 2 workers), kubeadm, Flannel CNI,
K8s v1.29.15.

### RBAC — least privilege

**File:** `k8s/rbac.yaml`

Two service accounts, not one:

| SA | Used by | Permissions |
|----|---------|------------|
| `pcam-inference` | Inference pods | None (`automountServiceAccountToken: false`) |
| `argocd-pcam-manager` | ArgoCD | Namespaced Role — only `pcam` namespace resources |

The inference pod never queries the Kubernetes API, so it gets no token at all.
ArgoCD gets a Role (not ClusterRole) scoped to the `pcam` namespace — it cannot touch
any other namespace. Both decisions follow the principle of least privilege.

CIS K8s Benchmark 5.1.5–5.1.6, ISO 27001:2022 A.9.

### Sealed Secrets

**Files:** `k8s/sealed-secret-rgw.yaml`, `k8s/sealed-secret-ghcr-pull.yaml`

Secrets are encrypted with the cluster's Sealed Secrets public key before committing:

```
plaintext secret → kubeseal (RSA-OAEP + AES-GCM) → SealedSecret YAML → git
                                                           ↓
                                                    controller decrypts
                                                    → K8s Secret in cluster
```

The ciphertext in git is useless without the cluster's private key.
This satisfies the GitOps requirement (everything in git) without storing plaintext
credentials. ISO 27001:2022 A.10 (cryptography).

GHCR credentials are split: the push token lives in GitHub Actions secrets (write:packages);
the pull token is sealed in the cluster (read:packages only). Principle of least privilege
applied to the registry layer.

### Probes — traffic gating for slow startup

The model download from RGW takes ~1–2 seconds on the LAN. Without a readiness probe,
Kubernetes would route traffic to the pod before the model is loaded.

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 15
  periodSeconds: 10

livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 30
  periodSeconds: 15
```

`/health` in `main.py` returns 200 only after the model is fully loaded into memory
(the `lifespan()` function sets a `model_ready` flag). The readiness probe blocks
traffic; the liveness probe restarts the pod if it hangs post-startup.

### HPA demo

```
Load test: 20 Locust users, 4/s ramp, 3 minutes, POST /predict

CPU utilisation: 1 × 396% (880m used / 250m requested)
HPA threshold:   80% CPU utilisation → target: 4 replicas at 396%
Scale event:     1 → 2 → 4 replicas within ~90 seconds
Scale-down:      back to 1 replica ~5 minutes after load stopped
```

The HPA `targetAverageUtilization` is 80% of the CPU *request* (250m). At 396%,
the controller calculates `ceil(1 × 3.96 / 0.80) = 5` but the max is 4, so it
caps at 4. Scale-down is intentionally slow (default 5-minute stabilisation window)
to avoid flapping.

Scale events are visible in the Grafana "HPA Replicas" panel and captured in
`load-test/hpa-watch.log`.

### Rolling update

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```

`maxUnavailable: 0` means at least one pod is always ready during a deploy —
critical when running at `replicaCount: 1` (the default). `maxSurge: 1` lets a
new pod come up and pull the model from RGW before the old pod is terminated.
Zero-downtime deploys even on a single-replica setup.

---

## 4. GitOps with ArgoCD

**File:** `k8s/argocd-application.yaml`

ArgoCD watches the `helm/pcam-inference/` directory on the `main` branch:

```yaml
source:
  repoURL: https://github.com/ahembal/portfolio
  targetRevision: HEAD
  path: p1-pcam-deployment/helm/pcam-inference
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

`selfHeal: true` means if someone manually edits a K8s resource (e.g.
`kubectl edit deployment`), ArgoCD immediately reverts it to match git.
The git repository is the only valid source of truth.

`prune: true` means resources removed from the Helm chart are deleted from
the cluster on the next sync, not left as orphans.

### What GitOps prevents

Without GitOps, a common failure mode is configuration drift: someone `kubectl apply`s
a hotfix, the change is never committed, and six months later nobody knows why the
running config differs from the repo. ArgoCD makes drift visible (sync status) and
self-healing (automated revert). Every cluster state change is a git commit with
author, timestamp, and diff.

---

## 5. Monitoring

**Directory:** `monitoring/`

Three files complete the observability layer:

| File | What it does |
|------|-------------|
| `prometheus-values.yaml` | kube-prometheus-stack Helm values — disables alertmanager, pins all monitoring pods to `quick-thrush`, sets emptyDir storage (no StorageClass on homelab) |
| `service-monitor.yaml` | Tells the prometheus-operator to scrape `pcam-pcam-inference` service at `/metrics` every 15s; carries `release: kube-prom` label required for operator discovery |
| `grafana-dashboard.yaml` | ConfigMap auto-discovered by Grafana sidecar; 5 panels covering request rate, error rate, latency percentiles, HPA replicas, pod CPU |

The prometheus-operator pattern means no manual Prometheus config file editing.
Adding a new service to scrape is a `kubectl apply -f service-monitor.yaml` — the
operator watches for ServiceMonitor CRDs and updates the scrape config automatically.
