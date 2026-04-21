# Q9 — Reflection: Kubernetes for ML Workloads

This is an honest account of where Kubernetes added value, where it created friction,
and what I would do differently. All observations are grounded in building this
specific project — not theory.

For the full debugging log, see `docs/deployment-troubleshooting.md`.
For the compliance mapping, see `docs/security-compliance.md`.

---

## What worked well

### GitOps makes deployments auditable by default

Every deployment change is a git commit: author, timestamp, diff, and a CI run that
proves the tests passed before the image was pushed. ArgoCD's `selfHeal: true` means
the cluster state converges to git automatically — nobody can quietly `kubectl edit`
something and forget to document it.

For an ML service this matters more than it might for a stateless web app. The model
version, the threshold values, the RGW endpoint, and the resource limits are all in
`values.yaml`. If a confidence threshold was changed two weeks ago and inference
results drifted, you can `git log` to find when and why.

### HPA handles bursty inference workloads cleanly

ML inference is CPU/GPU bound and bursty — idle most of the time, then suddenly
hammered by a batch upload or a demo. Horizontal autoscaling on CPU utilisation
(HPA, `targetAverageUtilization: 80`) scaled from 1 to 4 replicas within 90 seconds
under a 20-user Locust load test. Scale-down is slow by default (5-minute stabilisation
window), which avoids thrashing. This is the right model for inference: stateless pods,
no session affinity needed, scale out and back in.

### Sealed Secrets solves the "secrets in git" problem correctly

The alternative approaches are:
- Vault: correct but adds a dependency, operational complexity, and a new failure mode
- External Secrets Operator (ESO) with AWS SSM / GCP Secret Manager: correct but
  requires a cloud provider
- Plaintext in a private repo: wrong
- `.env` files on the server: wrong (not reproducible, not auditable)

Sealed Secrets encrypts with the cluster's RSA public key. The ciphertext is safe
to commit. Rotation requires re-sealing and re-committing — which is a git-audited
event. For a homelab or small team without a cloud provider, it is the right
complexity/security trade-off.

---

## Where Kubernetes added friction

### Six sequential pod startup crashes before the service ran

Each crash revealed the next problem, and each required a full image rebuild and push
(2–3 minutes per cycle):

| # | Error | Root cause |
|---|-------|-----------|
| 1 | `can't open file '/app/uvicorn'` | Distroless ENTRYPOINT is `python3.11`; CMD must use `-m uvicorn` not a bare binary |
| 2 | `getpwuid(): uid not found: 1000` | Distroless only has UID 65532; PyTorch calls `getpwuid()` to build its cache path |
| 3 | `IndexError: parents[2]` | Repo path vs. container path difference — `parents[2]` exists in repo, not in `/app` |
| 4 | `python-multipart not installed` | FastAPI needs this for `UploadFile`; not in requirements.txt |
| 5 | `fc.weight size mismatch [1,512] vs [2,512]` | Training used `num_classes=1`; serving default was `num_classes=2` |
| 6 | `SandboxChanged SIGTERM` | Flannel CNI crash on sought-perch — pods received SIGTERM from CNI sandbox rebuild |

None of these are Kubernetes bugs. But Kubernetes made the debug loop slower because:
- `kubectl logs` shows only the last crash, not a history
- A `docker run` test locally could have caught #1–#5 in one pass without pushes

**What I would do differently:** always test the image locally with `docker run`
before pushing. One local run with the actual env vars would have surfaced all five
application errors in one pass, without any cluster involvement. K8s should be the
last step, not the first.

### Probe tuning requires knowledge of startup time

The readiness probe fires at `initialDelaySeconds`. If that delay is shorter than
the model download + load time, the probe fires too early, fails, and Kubernetes
restarts the pod — masking whether the app itself is healthy. If it is too long,
deployments are slower than they need to be.

For this service, the model loads in ~2 seconds on the LAN. `initialDelaySeconds: 15`
is conservative but safe. The problem is that "startup time" is not a fixed number:
it depends on network speed (RGW download), CPU allocation (torch model loading is
CPU bound), and whether the torch JIT cache is warm. These vary between environments.

A better pattern would be a startup probe (separate from readiness) that polls until
the model is loaded, then hands off to readiness and liveness. FastAPI's `/health`
already signals readiness; the missing piece is a startup probe with a higher failure
threshold and longer period to cover slow-start scenarios without racing readiness.

### CNI instability masked application health

The Flannel VXLAN bug on `sought-perch` (kernel 6.8.0-101) caused the CNI to crash
every ~7 minutes and rebuild the network sandbox, sending SIGTERM to all pods on the
node. The pod crash log looked identical to a clean shutdown — exit code 0, no error
message. The real signal was the `SandboxChanged` K8s event, not the application log.

This took significant time to diagnose because the evidence was in two separate places:
the K8s event stream (`kubectl get events`) and the Flannel pod logs — not in the
application logs where I was looking first.

**Lesson:** when a pod crashes with a clean exit and the application log shows nothing
wrong, look at K8s events and node-level infrastructure before suspecting the application.

### GitOps overhead is real for a single-model service

ArgoCD adds:
- A running deployment in the cluster consuming RAM (~500 MB)
- A DNS dependency (ArgoCD needs to reach GitHub to pull the repo)
- A secrets dependency (GHCR pull token, repo access token)
- Debugging surface: ArgoCD's own components can crash (dex-server, applicationset-controller,
  repo-server TLS — all required fixes in this project)

For a single model, a single environment, and a one-person team, `helm upgrade` in CI
is simpler and has fewer moving parts. The GitOps model pays off at scale: multiple
services, multiple environments, a team that needs audit trails and self-healing
reconciliation. For this project, the GitOps overhead was justified as a learning
exercise and portfolio demonstration, not because it was the minimal solution.

---

## What Kubernetes does not solve for ML

### Model versioning and registry

Kubernetes manages *application* versions (image tags). It has no concept of *model*
versions — which checkpoint corresponds to which training run, what metrics it achieved,
whether it passed evaluation gates before promotion. That layer lives outside K8s:
- In this project: model key in RGW + metrics in `metrics.json` + threshold in `threshold.json`
- In production: MLflow, W&B, or a purpose-built model registry

Kubernetes knows "image tag `abc123` is deployed." It does not know "model `kaggle-001`
with AUC 0.9657 is serving." Those are two different versioning dimensions and they
need to be tracked separately.

### Data drift and model monitoring

Prometheus tracks request rate, latency, and error rate. These are service health
metrics. They do not tell you whether the model's predictions are drifting — whether
the distribution of incoming patches has shifted from the training distribution, or
whether the confidence scores are degrading over time.

Model monitoring requires tracking the distribution of output probabilities over time
and comparing them to a baseline. This is not something `kube-state-metrics` or
`node-exporter` provides. It requires either:
- A custom metric (e.g. `histogram_quantile` on the confidence score)
- A dedicated drift detection tool (Evidently, WhyLogs, Arize)

The Grafana dashboard in this project covers service health. Model health monitoring
is a gap acknowledged in `docs/security-compliance.md` §1 (EU AI Act Art. 72 —
post-market monitoring).

### GPU scheduling

This service runs on CPU (ResNet-18 inference at ~350ms/patch on CPU is acceptable
for a demo). Production ML inference at scale needs GPU scheduling — Kubernetes
supports this via `nvidia.com/gpu` resource limits and the NVIDIA device plugin, but
the default scheduler has no awareness of GPU memory fragmentation or MIG partitioning.
Frameworks like NVIDIA Triton Inference Server, Ray Serve, or KServe (KFServing)
address this at the serving layer; Kubernetes provides the substrate.

---

## EU AI Act — what the deployment would need at production scale

PCam classifies histopathology patches for cancer detection. Under EU AI Act Annex III,
this is **high-risk AI** (AI systems used as safety components of medical devices).

Current state addresses:
- Art. 11 (technical documentation): training metrics, threshold selection rationale,
  model versioning all documented
- Art. 15 (accuracy/robustness): AUC 0.9657, dual thresholds with documented
  sensitivity/specificity
- Art. 72 (post-market monitoring): Prometheus + Grafana for service-level metrics

Gaps before clinical deployment:
- **Art. 9 (risk management system):** formal risk register, iterative review process
- **Art. 14 (human oversight):** operator review step before any autonomous clinical action
- **Art. 35 GDPR (DPIA):** required before processing real patient data
- **EU MDR:** if deployed as a medical device, full conformity assessment required

The fact that these gaps are known and documented is itself part of responsible AI
development per ISO/IEC 42001:2023 (AI management system) and NIST AI RMF 1.0.

---

## Summary

Kubernetes is good infrastructure for ML serving once the application is working.
It is a poor debugging environment for an application that is not yet working,
because the build-push-deploy loop is slow and infrastructure failures (CNI crashes,
probe misconfiguration) can look identical to application failures.

The right sequence is:
1. Get the application working locally (`docker run` with the same env vars)
2. Deploy to Kubernetes once the image is confirmed healthy
3. Add GitOps/ArgoCD when the deployment is stable and you need audit trails or
   multi-environment management

The value is real — autoscaling, zero-downtime deploys, secrets management,
observability, GitOps audit trail. The cost is also real — operational complexity,
debugging indirection, and several components that can independently fail. It is
the right tool for a production ML service; it may not be the right tool for
a single-developer prototype.
