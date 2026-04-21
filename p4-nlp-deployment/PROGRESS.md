# Project 4 — NLP Deployment
## Progress Tracker
*Last updated: 2026-04-21*

---

## Steps

### Phase 1 — Training
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | notebooks/train_pubmed_rct.ipynb | ⬜ Todo | Kaggle notebook: load PubMed RCT from HuggingFace Hub, fine-tune DistilBERT with Trainer API, save best checkpoint. This is where the model comes from — everything downstream depends on having trained weights. |
| 2 | Evaluate + record metrics | ⬜ Todo | Accuracy, macro F1, per-class F1 on test set. These numbers go into the Q4/Q5 docs as evidence of real performance. Target ≥ 85% accuracy (DistilBERT without domain tuning baseline). |
| 3 | Push model to Ceph RGW | ⬜ Todo | Upload model weights + tokenizer to `s3://nlp-models/pubmed-rct/kaggle-001/`. Same RGW pattern as p1 — serving pulls from here at startup, so the image stays small and model versioning is decoupled from code. |

### Phase 2 — Serving
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | serving/main.py | ⬜ Todo | FastAPI app: loads DistilBERT tokenizer + model from RGW at startup (lifespan pattern). `/predict` accepts a text string, tokenises, runs inference, returns label + confidence + latency_ms. Multi-class: softmax + argmax (unlike p1 which used sigmoid). |
| 5 | serving/requirements.txt | ⬜ Todo | transformers, torch, fastapi, uvicorn, boto3, prometheus-client — pinned. HuggingFace Transformers adds ~500 MB to the image; multi-stage build keeps the runtime layer lean. |
| 6 | serving/Dockerfile | ⬜ Todo | Multi-stage distroless. Key difference from p1: `TRANSFORMERS_CACHE=/tmp/hf_cache` must be set — HuggingFace tries to write a cache at import time and distroless has no writable paths outside /tmp. |
| 7 | Local docker run test | ⬜ Todo | Run the image with real env vars before touching K8s. Lesson from p1: test locally first — 6 pod crash cycles could have been caught in one local run. Confirm `/predict` returns the correct label for known sentences. |

### Phase 3 — Streamlit demo
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | streamlit/app.py | ⬜ Todo | UI that calls the FastAPI `/predict` endpoint. User pastes a PubMed abstract, app splits into sentences, classifies each, colour-codes by label (Background=blue, Methods=green, etc.). Makes the model tangible for reviewers who won't curl an API. |
| 9 | Add streamlit to docker-compose | ⬜ Todo | `streamlit` service calls `api` service by Docker Compose service name. One `docker compose up` runs the full demo. Required for local end-to-end testing before K8s deployment. |

### Phase 4 — Helm + K8s + CI/CD
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 10 | helm/nlp-inference/ chart | ⬜ Todo | Same structure as p1 (deployment, service, configmap, HPA). Two deployments: nlp-api and nlp-streamlit. Streamlit calls the API via in-cluster ClusterIP service — no external routing between them. |
| 11 | Sealed Secrets for RGW creds | ⬜ Todo | Same kubeseal pattern as p1. Shows the pattern is reusable infrastructure, not a one-off. |
| 12 | GitHub Actions CI | ⬜ Todo | pytest → docker build × 2 (api image + streamlit image) → push GHCR → update values.yaml with new tags. Two images because api and streamlit have different dependencies and update at different rates. |
| 13 | ArgoCD Application CR | ⬜ Todo | Watches helm/nlp-inference/ on main branch. Auto-deploys on values.yaml tag change from CI. |

### Phase 5 — Tests + Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 14 | tests/test_nlp_inference.py | ⬜ Todo | Unit tests: tokenisation output shape, label mapping correctness, preprocessing edge cases (empty string, very long input). Integration test with a mocked model to verify the inference→response pipeline without needing GPU. |
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
