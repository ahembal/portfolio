# Production Readiness Gap Analysis
*Last updated: 2026-05-05*

An honest assessment of what separates the current portfolio from a genuinely
production-grade system. Not a todo list — a gap analysis. Each item notes
what's missing, why it matters in production, and effort to fix.

---

## ML Quality (p6 Research Agent)

| Gap | Why it matters in production | Effort |
|-----|------------------------------|--------|
| LLM stops after single tool call | Agent answers from paper titles only — claims are not grounded in actual abstract content. Fix: update system prompt to require `pubmed_fetch` before citing. | Low |
| Hallucinated citations | LLM generates PMID/UniProt accessions from memory without retrieving them. Provenance check is implemented but not yet deployed. | Low |
| No faithfulness scoring | Validation checks provenance (was the identifier retrieved?) but not faithfulness (does the claim match what was retrieved?). Requires LLM-as-judge pipeline — planned for p7. | High |
| Title-only grounding not blocked | A PMID can be cited after `pubmed_search` without `pubmed_fetch`. The abstract was never read. Warning is surfaced but answer is not blocked. | Medium |
| p6: non-English PubMed results | Results may include non-English abstracts. The LLM may silently produce an incorrect summary. Fix: add `AND English[Language]` to Entrez query. | Low |

See `p6-research-agent/docs/answer-quality.md` for full details.

---

## Security

| Gap | Why it matters in production | Effort |
|-----|------------------------------|--------|
| No image signing (cosign/sigstore) | Without signing, a compromised registry could serve a tampered image and K8s would deploy it. SLSA L3 / NIST 800-190 requirement. | Medium |
| No SBOM generation | Supply chain attacks target transitive dependencies. An SBOM (syft/trivy) makes the full dependency tree auditable. EO 14028 requirement for US government. | Low |
| No vulnerability scanning in CI | CVEs in base images are not caught before deployment. Trivy/Grype scan in CI catches known vulnerabilities at build time. | Low |
| Network policies removed | ArgoCD CNI instability required removing NetworkPolicies (see runbooks). Without them, any pod can reach any other pod across namespaces. | Medium |
| No TLS on ingress | Services are exposed via NodePort without TLS. In production, all external traffic should terminate TLS at the ingress layer. | Medium |
| GHCR_TOKEN in .bashrc | Personal PAT with write:packages scope stored in plaintext. Should be rotated and stored only in pass/vault. Noted in TODO.local. | Low |
| sought-perch node (ISS-009) | Cordoned node with unknown kube-proxy failure root cause. In production, all nodes must be healthy and schedulable. | Unknown |
| API server TLS SAN | kubectl over Tailscale still uses insecure-skip-tls-verify in one kubeconfig context. Proper fix: add Tailscale IP to cert SANs. | Low |

---

## Observability

| Gap | Why it matters in production | Effort |
|-----|------------------------------|--------|
| No Grafana dashboard for p6 | p1 and p2 have dashboards; p6 (the most complex service) has none. No visibility into query latency, tool call frequency, or Ollama inference time. | Medium |
| No Grafana dashboard for p4 | Once p4 serving is built, it needs latency/throughput monitoring. | Low (reuse p1 template) |
| No alerting rules | Prometheus metrics exist but no alerts are configured. In production, on-call requires alerts for SLO breaches. | Medium |
| No structured logging | All services log to stdout in human-readable format. Production observability requires structured JSON logs with correlation IDs for distributed tracing. | Medium |
| No distributed tracing | Multi-hop requests (Streamlit → API → Ollama → PubMed) have no trace correlation. OpenTelemetry would connect them. | High |

---

## Reliability

| Gap | Why it matters in production | Effort |
|-----|------------------------------|--------|
| No model calibration (p1, p4) | Confidence scores are not calibrated probabilities. A score of 100% does not mean 100% certainty — it means a large logit. Temperature scaling is a one-afternoon fix. See `p1/docs/model-limitations.md §3`. | Low |
| p6 agent is synchronous | `graph.invoke()` blocks the event loop. Fixed with `run_in_executor` but the deeper solution is `graph.astream()` with SSE streaming. | Medium |
| No retry logic on external APIs | PubMed and UniProt calls have no retry on transient failures. A single timeout drops the whole query. | Low |
| Single replica for all services | All deployments run 1 replica. Production requires at minimum 2 for zero-downtime rolling updates. | Low |
| No readiness probe on p6 API | The liveness probe exists but no readiness probe — K8s may route traffic before the graph is initialised. | Low |
| Ollama model not pre-pulled | On pod restart the model must be re-pulled from the internet (~4 GB). A warm PVC helps but doesn't survive PVC deletion. | Low |
| p6: non-English PubMed results | `pubmed_search()` returns papers in any language. The LLM may silently produce an incorrect summary of a non-English abstract. Fix: add `AND English[Language]` to the Entrez query. | Low |

---

## CI/CD

| Gap | Why it matters in production | Effort |
|-----|------------------------------|--------|
| GitHub Actions on Node.js 20 | Node.js 20 is deprecated in Actions from June 2026. Upgrade `actions/checkout` and `docker/login-action` to latest versions. | Low |
| No staging environment | Changes go directly from CI to production (the cluster). A staging namespace with smoke tests between CI and production is standard practice. | High |
| No rollback automation | ArgoCD can sync forward but rollback requires a manual git revert or ArgoCD UI action. Automated rollback on health check failure is a production requirement. | Medium |
| Race condition in update-tags | Fixed with `git pull --rebase` but still brittle when multiple CI runs overlap. A better pattern is a dedicated bot branch or a tag file per service. | Medium |
| No canary or blue-green deployments | Rolling updates are all-or-nothing. Production ML serving typically requires canary (route 5% traffic to new model, monitor, then promote). | High |

---

## Incomplete projects

| Project | What's missing | Impact |
|---------|---------------|--------|
| p4 NLP deployment | Serving layer (FastAPI), Streamlit UI, Helm chart, CI/CD — only the model is trained | p4 cannot be demonstrated end-to-end |
| p5 Dev practices site | Lovable/React site not built — content and prompt are ready | p5 has no live demo |
| p3 GPU benchmark | Dardel down for electrical upgrade — cuDF/ROCm results pending | Benchmark is incomplete without GPU comparison |
| p6 real-time streaming | Agent trace appears after completion — no live step-by-step updates during inference | User experience significantly better with streaming |
| p1/p6 real PCam demo images | Current samples are PathMNIST (wrong tissue type). Kaggle notebook exists to extract real ones. | Demo predictions are unreliable |

---

## Infrastructure

| Gap | Why it matters in production | Effort |
|-----|------------------------------|--------|
| Single control-plane node | `clever-fly` is the only control-plane node. If it fails, the cluster is unmanageable (workloads keep running but no new deployments). Production requires 3 control-plane nodes. | High |
| Cluster DNS not updated | MAAS DHCP still hands out old DNS IP in some cases. Causes intermittent CoreDNS failures. | Low |
| No cluster backup | No etcd snapshots scheduled. A control-plane failure would require rebuilding the cluster from scratch. | Medium |
| Ceph single-node risk | RGW and RBD depend on the Ceph cluster. Current setup has limited redundancy for a homelab. | High |
| No Kubernetes version upgrade plan | Cluster runs 1.29. Production clusters require a tested upgrade path for each minor version. | Medium |
