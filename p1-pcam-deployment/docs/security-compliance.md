# Security & Compliance Standards — PCam Inference Service

This document maps every significant security, quality, and AI governance decision
in the project to the standard or regulation that motivated it. It is a living
reference: when a decision is changed, the relevant entry here should be updated.

---

## Standards reference

| Standard | Scope | Version / date |
|----------|-------|----------------|
| EU AI Act | AI system classification, obligations | In force Aug 2024 |
| ISO/IEC 42001 | AI management system | 2023 |
| ISO/IEC 23894 | AI risk management | 2023 |
| ISO/IEC 5338 | AI system lifecycle processes | 2023 |
| NIST AI RMF | AI risk management framework | 1.0 — 2023 |
| ISO/IEC 27001 | Information security management | 2022 revision |
| ISO/IEC 27002 | InfoSec controls guidance | 2022 |
| NIST SP 800-190 | Container security | Rev 1 |
| NIST CSF | Cybersecurity framework | 2.0 — Feb 2024 |
| CIS Kubernetes Benchmark | K8s hardening | v1.9 |
| SLSA | Software supply chain security | v1.0 — 2023 |
| ISO 9001 | Quality management | 2015 |
| ISO/IEC 25010 | Software product quality | 2023 revision |
| GDPR / Article 9 | Personal & special-category data | EU 2016/679 |

---

## 1. EU AI Act — high-risk classification

**Status: prototype / research — not yet subject to full conformity obligations.
This section documents what would be required for a regulated deployment.**

PCam classifies histopathology tissue patches for cancer detection. Under
EU AI Act Annex III §5 (AI systems used as safety components of medical devices,
or themselves constituting medical devices), a production deployment assisting
clinical diagnosis would be **high-risk**.

High-risk obligations that apply at production:

| Obligation | Article | Current state | What is needed |
|-----------|---------|---------------|----------------|
| Risk management system | Art. 9 | Partial — eval metrics documented | Formal risk register, iterative review |
| Data governance | Art. 10 | PCam dataset is public and de-identified | PII/GDPR review if real patient data used |
| Technical documentation | Art. 11 | PROGRESS.md, Q5/Q7/Q9 docs | Full conformity file |
| Human oversight | Art. 14 | No override mechanism | Operator review step before acting on output |
| Accuracy & robustness | Art. 15 | AUC 0.9657, F1 0.897 documented | Formal threshold validation against intended population |
| Post-market monitoring | Art. 72 | Prometheus/Grafana dashboards | Drift detection, retraining trigger |

**Relevant design decisions already aligned with EU AI Act:**
- Model metrics (AUC, F1, sensitivity/specificity, Youden threshold) are recorded
  in PROGRESS.md and `train/metrics.json` → supports Art. 11 documentation.
- Prometheus monitoring with latency and error-rate dashboards → supports Art. 72
  post-market monitoring.
- Model is versioned by `run-id` in RGW (`pcam/kaggle-001/best_model.pt`) → supports
  traceability of which model version is serving.

---

## 2. ISO/IEC 42001:2023 — AI management system

ISO 42001 defines requirements for an AI management system (AIMS), complementing
ISO 27001 with AI-specific concerns: bias, explainability, data quality, model
lifecycle.

| 42001 Clause | Decision | Location |
|-------------|----------|----------|
| 6.1 — Risks & opportunities | Two inference thresholds chosen: Youden (balanced) and 95%-sensitivity (safety-first) | `train/metrics.json`, PROGRESS.md |
| 8.4 — Data for AI systems | PCam dataset is public, CC-BY 4.0, de-identified — provenance documented | PROGRESS.md §Kaggle run details |
| 8.5 — AI system development | ResNet-18, ImageNet pretrained, 6-epoch training, augmentation strategy documented | `train/train.py`, Kaggle notebook |
| 9.1 — Performance evaluation | AUC, Accuracy, F1, loss curves logged per epoch | `train/metrics.json` |
| 10.2 — Continual improvement | Model versioned in RGW; IMAGE_TAG updated by CI on each rebuild | CI pipeline, `helm/values.yaml` |

---

## 3. ISO/IEC 23894:2023 — AI risk management

Key risks identified and mitigated:

| Risk | Mitigation |
|------|-----------|
| Distribution shift (production data ≠ PCam dataset) | Documented as known gap; Prometheus error-rate panel as detection signal |
| Adversarial inputs (malformed or manipulated patches) | Input validated as PNG image; model output is label + confidence score, not autonomous action |
| Model confidence misinterpretation | Confidence score returned alongside label; README warns dummy weights produce confidence=1.0 |
| Single point of failure | HPA scales 1→4 pods; rolling update ensures zero-downtime deployment |

---

## 4. ISO/IEC 27001:2022 — Information security

### A.5 — Organizational controls
- **A.5.1 Policies**: This document + `deployment-troubleshooting.md` serve as
  project-level security policy documentation.

### A.8 — Technology controls (2022 additions relevant here)
- **A.8.4 Access to source code**: Repository is private; CI uses scoped tokens
  (write:packages for push, read:packages for pull — separate credentials).
- **A.8.8 Management of technical vulnerabilities**: Distroless runtime base
  eliminates the OS package surface. Trivy/Snyk scans referenced in Dockerfile.
  `requirements.txt` is pin-locked via `pip-compile` for reproducible dep versions.
- **A.8.9 Configuration management**: All configuration is in Git (Helm values,
  K8s manifests, CI workflow). No manual cluster changes — GitOps as the control.
- **A.8.25 Secure development lifecycle**: Multi-stage Docker build, non-root
  container user, explicit secret injection (not env dump), probe-gated traffic.

### A.9 — Access control
- Dedicated `pcam-inference` ServiceAccount with `automountServiceAccountToken: false`
  (`k8s/rbac.yaml`). Inference pods cannot query the K8s API.
- ArgoCD service account scoped to a namespaced `Role` (not `ClusterRole`).
  It can only manage resources in the `pcam` namespace.
- GHCR credentials split: write token in CI secrets (GitHub Actions), read token
  sealed in cluster as `ghcr-pull-secret`. Principle of least privilege.

### A.10 — Cryptography
- RGW credentials and GHCR pull token encrypted at rest using Bitnami Sealed Secrets
  (`k8s/sealed-secret-rgw.yaml`, `k8s/sealed-secret-ghcr-pull.yaml`).
- Sealed Secrets uses asymmetric encryption (RSA-OAEP + AES-GCM); only the
  cluster's controller private key can decrypt. Safe to commit ciphertext to Git.

---

## 5. NIST SP 800-190 — Container security

NIST 800-190 defines controls across image, registry, orchestration, and host layers.

| Control area | Decision | Evidence |
|-------------|----------|---------|
| Image — minimal base | `gcr.io/distroless/python3-debian12:nonroot` — no shell, no package manager | `serving/Dockerfile` |
| Image — non-root user | UID 65532 (`nonroot` in distroless) | `Dockerfile`, `deployment.yaml` securityContext |
| Image — dep pinning | `pip-compile` generated `requirements.txt` with pinned hashes | `requirements.txt` |
| Registry — access control | Separate write (CI) / read (cluster) tokens; GHCR private registry | `k8s/sealed-secret-ghcr-pull.yaml` |
| Orchestrator — least privilege | Namespaced RBAC Role, no ClusterRole, `automountServiceAccountToken: false` | `k8s/rbac.yaml` |
| Orchestrator — secrets management | Sealed Secrets (encrypted in Git, decrypted by controller) | `k8s/sealed-secret-*.yaml` |
| Runtime — resource limits | CPU/memory requests and limits set on every container | `helm/values.yaml`, `deployment.yaml` |
| Runtime — probes | Liveness + readiness probes; traffic only after model loaded | `deployment.yaml` |

**Gap / deferred:** Image signing (Sigstore/cosign) not yet implemented.
Signing would provide cryptographic provenance: CI attests each built image,
cluster verifier rejects unsigned images. Aligns with SLSA L3 and NIST 800-190 §4.2.

---

## 6. NIST CSF 2.0 — Cybersecurity framework

CSF 2.0 (Feb 2024) introduced the **Govern** function alongside Identify / Protect /
Detect / Respond / Recover.

| Function | Implementation |
|---------|---------------|
| **Govern** | GitOps as change control: every deployment change is a reviewed, committed, and auditable Git event. This document as policy record. |
| **Identify** | Asset inventory implicit in Helm chart + K8s manifests. Model versioning in RGW. |
| **Protect** | Sealed Secrets, RBAC, non-root containers, distroless image, network isolation (ClusterIP service). |
| **Detect** | Prometheus scraping `/metrics`; Grafana dashboard with error-rate and latency panels; HPA scaling events visible in `hpa-watch.log`. |
| **Respond** | Rolling update strategy (`maxUnavailable: 0`) enables zero-downtime rollback via `helm rollback`. |
| **Recover** | Model pulled from RGW at startup — pod restart is a full recovery. emptyDir Prometheus storage accepted as a demo trade-off (data lost on pod restart). |

---

## 7. CIS Kubernetes Benchmark v1.9

Controls already satisfied:

| CIS control | Decision |
|------------|---------|
| 5.1.5 — No default SA token in pods | `automountServiceAccountToken: false` on `pcam-inference` SA |
| 5.1.6 — Ensure SA tokens are not auto-mounted | Same; explicit per-pod override not needed |
| 5.2.2 — Do not admit privileged containers | No `privileged: true` anywhere in manifests |
| 5.2.6 — Do not admit containers with `allowPrivilegeEscalation` | Not set (defaults false in our security context) |
| 5.2.7 — Do not admit root containers | `runAsNonRoot: true`, `runAsUser: 65532` in deployment spec |
| 5.7.1 — Create namespaces | `pcam` namespace explicitly created in `rbac.yaml` |

**Gap / deferred:**
- 4.2.6 — Read-only root filesystem (`readOnlyRootFilesystem: true`) not yet set.
  Blocked by PyTorch needing `/tmp/torchinductor` writable; workaround via
  `TORCHINDUCTOR_CACHE_DIR`. Can be enabled once a writable `emptyDir` volume
  mount is added for that path.
- Network policies — removed during ArgoCD troubleshooting (see `deployment-troubleshooting.md` §1);
  should be reinstated for production.

---

## 8. SLSA v1.0 — Supply chain security

SLSA (Supply-chain Levels for Software Artifacts) defines provenance requirements
for build pipelines.

| Level | Requirement | Status |
|-------|------------|--------|
| L1 — Provenance exists | Build script in version control (`.github/workflows/`) | ✅ |
| L1 — Build defined in code | `Dockerfile` and CI workflow both committed | ✅ |
| L2 — Hosted build service | GitHub Actions (hosted runner) performs the build | ✅ |
| L2 — Provenance authenticated | GHCR image tagged with git SHA | ✅ |
| L3 — Hardened build | Hermetic build, no network during build, signed provenance | ❌ Deferred |

Current state maps to **SLSA Build L2**. Reaching L3 would require:
- Hermetic build environment (no external network calls during `docker build`)
- Sigstore/cosign provenance attestation pushed alongside the image
- SLSA verifier in the cluster (e.g. Kyverno policy checking cosign signature)

---

## 9. GDPR & medical data

PCam uses the PatchCamelyon dataset (derived from Camelyon16 challenge), which
contains de-identified histopathology slides with no patient-identifiable information.
**As used here, GDPR Article 9 (special category data) obligations do not apply.**

If this system were deployed against real patient data:
- Article 9(2)(h) — processing for medical purposes requires explicit consent or
  a legal basis under national law.
- Article 25 — data protection by design: inference API should not log input images;
  only metadata (latency, label, confidence) should be retained.
- Article 17 — right to erasure: model training data provenance must be traceable
  so specific individuals' data can be excluded from future retraining.
- Article 35 — DPIA (Data Protection Impact Assessment) required before deployment.

**Design decisions already aligned:**
- The `/predict` endpoint does not log or persist the input image.
- Only aggregate metrics (request count, latency histogram) are exported to Prometheus.

---

## 10. ISO 9001:2015 — Quality management

| ISO 9001 clause | Implementation |
|----------------|---------------|
| 7.5 — Documented information | PROGRESS.md, this doc, `deployment-troubleshooting.md`, Q5/Q7/Q9 docs |
| 8.1 — Operational planning | Steps defined upfront in PROGRESS.md; status tracked per step |
| 8.5.6 — Control of changes | All changes via Git commits; CI enforces tests before image push |
| 9.1 — Monitoring & measurement | Prometheus metrics, Grafana dashboard, HPA scaling events logged |
| 10.2 — Nonconformity & corrective action | `deployment-troubleshooting.md` documents each failure mode and its fix |

---

## 11. ISO/IEC 25010:2023 — Software product quality

The 2023 revision of the SQuaRE quality model added AI-specific characteristics.
Evidence for each characteristic:

| Quality characteristic | Evidence |
|-----------------------|---------|
| Functional correctness | pytest suite, /predict returns label + confidence |
| Performance efficiency | Latency histogram (p50/p95/p99), HPA for throughput |
| Reliability | Rolling update (`maxUnavailable: 0`), liveness/readiness probes |
| Security | Distroless, non-root, RBAC, Sealed Secrets |
| Maintainability | Helm chart (parameterised), GitOps (reproducible), pinned deps |
| **AI accuracy** (new 2023) | AUC 0.9657, Accuracy 90.0%, F1 0.897, dual thresholds |
| **AI safety** (new 2023) | Confidence score returned; no autonomous clinical action taken |

---

## Deferred / out-of-scope items

| Item | Reason deferred | Reference |
|------|----------------|-----------|
| Image signing (cosign) | Not yet configured in CI | SLSA L3, NIST 800-190 |
| SBOM generation (syft/trivy) | pip-compile provides manual SBOM; formal SBOM deferred | EO 14028 |
| Read-only root filesystem | PyTorch inductor cache needs writable /tmp | CIS 5.2.x |
| Network policies | Removed for homelab CNI stability | CIS, ISO 27001 A.8 |
| API server TLS SAN fix | Tailscale IP not in cert SANs; tracked in PROGRESS.md §17 | General |
| MDR / FDA SaMD conformity | Research prototype; not intended for clinical use | EU MDR, FDA SaMD |
| Formal DPIA | No real patient data in current deployment | GDPR Art. 35 |
