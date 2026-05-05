# Project 4 — NLP Deployment
## Progress Tracker
*Last updated: 2026-04-28*

---

## Cluster constraints
> See `runbooks/known-issues.md` for full details.
- **Model training:** on HPC (Dardel/UPPMAX) or Kaggle — not on homelab cluster
- **Serving + Streamlit:** deploy on `quick-thrush` (stable worker, 64 GB RAM)
- `sought-perch` is cordoned — do not schedule there (ISS-009)
- Copy `ghcr-pull-secret` to the new namespace before deploying
- Use full SHA image tags in Helm values (not short SHA) — see ISS-007
- Postgres/stateful volumes: use `subPath` in volumeMount (ext4 lost+found issue)
- Serving is CPU inference (~250 MB model) — no GPU needed in K8s, GPU only for training

---

## Steps

### Phase 1 — Training
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | notebooks/train_pubmed_rct.ipynb | ✅ Done | DistilBERT is 40% smaller and 60% faster than BERT at 97% of its NLP benchmark performance — right for CPU serving where inference latency matters. Fine-tuning on PubMed abstracts is necessary because general-purpose models don't understand biomedical sentence structure (BACKGROUND / METHODS / RESULTS / CONCLUSIONS / OBJECTIVE are domain-specific categories). |
| 2 | Evaluate + record metrics | ✅ Done | Macro F1 (not just accuracy) is the correct primary metric because classes are imbalanced and all class errors matter equally — a model that ignores OBJECTIVE entirely would score well on accuracy but poorly on F1. Per-class breakdown shows where the model is weakest (OBJECTIVE=0.640) which informs where additional training data would help most. |
| 3 | Push model to Ceph RGW | ✅ Done | The two-step path (Kaggle → HuggingFace Hub → RGW) is the correct workaround for Kaggle's network environment — Kaggle runs in Google Cloud where private Tailscale IPs are not routable. HuggingFace Hub is a neutral public intermediary. The model must be in RGW so the serving container can pull it at startup without bundling it in the image. |

### Phase 2 — Serving
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | serving/main.py | ✅ Done | FastAPI app: loads DistilBERT tokenizer + model from RGW at startup (lifespan pattern). `/predict` accepts a text string, tokenises, runs inference, returns label + confidence + latency_ms. Multi-class: softmax + argmax (unlike p1 which used sigmoid). |
| 5 | serving/requirements.txt | ✅ Done | transformers, torch, fastapi, uvicorn, boto3, prometheus-client — pinned. HuggingFace Transformers adds ~500 MB to the image; multi-stage build keeps the runtime layer lean. |
| 6 | serving/Dockerfile | ✅ Done | Multi-stage distroless. Key difference from p1: `TRANSFORMERS_CACHE=/tmp/hf_cache` must be set — HuggingFace tries to write a cache at import time and distroless has no writable paths outside /tmp. |
| 7 | Local docker run test | ⬜ Skipped | Tests pass locally (10/10). Docker build skipped locally — torch download (~2GB) too slow. CI handles the build. All known failure modes (getpwuid, cache dirs, securityContext) pre-emptively fixed based on p1/p6 experience. |

### Phase 3 — Streamlit demo
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | streamlit/app.py | ✅ Done | Added as a page in the portfolio Streamlit UI (p6-research-agent/streamlit/pages/2_NLP_Classifier.py). User pastes a PubMed abstract, each sentence is colour-coded by label. Separate Streamlit deployment not needed — the portfolio UI already serves all projects. |
| 9 | Add streamlit to docker-compose | ⬜ N/A | Not needed — UI is part of the portfolio Streamlit, not a separate service. |

### Phase 4 — Helm + K8s + CI/CD
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 10 | helm/nlp-inference/ chart | ✅ Done | Deployment, service, configmap, ArgoCD Application CR. securityContext + readiness probe applied from the start. |
| 11 | Sealed Secrets for RGW creds | ⬜ Todo | Same kubeseal pattern as p1. Shows the pattern is reusable infrastructure, not a one-off. |
| 12 | GitHub Actions CI | ✅ Done | test → build → push GHCR → update values.yaml SHA. Same pattern as p1/p2/p6. |
| 13 | ArgoCD Application CR | ✅ Done | In helm/nlp-inference/templates/argocd-application.yaml. Watches helm/nlp-inference/ on main. |

### Phase 5 — Tests + Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 14 | tests/test_nlp_inference.py | ✅ Done | 10 tests, all passing. Mocked model returns fixed logits — no GPU or RGW needed. Covers health, predict, empty input, 503 when model not loaded. |
| 15 | docs/q4-personal-abilities.md | ⬜ Todo | Explains what this project demonstrates about independent ML capability: dataset choice, why DistilBERT over BERT, evaluation methodology, end-to-end deployment decisions made without a template or guided exercise. |
| 16 | docs/q5-nlp-deploy.md | ⬜ Todo | Deployment walkthrough focusing on what differs from image classification (p1): tokeniser pipeline, variable-length input padding/truncation, model size (~250 MB vs ~45 MB), batching strategy. Same GitOps pattern, different model characteristics. |

---

## Quick status

```
Phase 1  [░░░]  0/3  ← start here
Phase 2  [░░░░] 0/4
Phase 3  [░░]   0/2
Phase 4  [░░░░] 0/4
Phase 5  [░░░]  0/3
```
