# P4 — NLP Deployment — Spec

> Last updated: 2026-04-21

## What this project is

Fine-tune a transformer model on a medical NLP task, then deploy it with the same
production patterns used in p1 — FastAPI serving, Docker, K8s via Helm, GitOps.

**Task:** Sentence classification on the PubMed RCT dataset — given a sentence from a
medical abstract, classify it as one of: Background, Objective, Methods, Results,
Conclusions. This is a real NLP benchmark (PubMed 200k RCT, Dernoncourt & Lee 2017)
with a clear evaluation metric (accuracy / F1 per class).

**Portfolio questions answered:**
- Q4 — Personal abilities: demonstrates independent end-to-end ML work — dataset,
  training, evaluation, deployment, demo UI — without scaffolding
- Q5 — NLP-specific deployment: contrasts with p1 (image classification) to show
  breadth; same GitOps/serving pattern applied to a different modality

**Why this dataset and task?**
PubMed RCT is publicly available, small enough to fine-tune on a free Kaggle T4 GPU
in under an hour, has a clear benchmark baseline (BioBERT achieves ~92% accuracy),
and is medically relevant — consistent with the EU AI Act / compliance angle from p1.

---

## Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Model | DistilBERT-base-uncased | 40% smaller than BERT-base, ~97% of performance, fits in Kaggle T4 RAM |
| Fine-tuning | HuggingFace Transformers + Trainer API | Standard; handles mixed precision, gradient accumulation, evaluation loop |
| Compute | Kaggle T4 GPU | Same as p1; no new infra needed |
| Serving | FastAPI (same pattern as p1) | Loads model from Ceph RGW at startup, `/predict`, `/health`, `/metrics` |
| Demo UI | Streamlit | Lets the reviewer paste an abstract and see sentence-level classification — makes the model tangible |
| Container | distroless (same as p1) | Consistent security posture across projects |
| K8s | Helm chart | Same GitOps pattern; shows the pattern is reusable, not one-off |

---

## Model output

```
Input:  "Patients were randomly assigned to receive either drug A or placebo."
Output: { "label": "Methods", "confidence": 0.94, "latency_ms": 45 }
```

Multi-class (5 classes), so softmax + argmax — unlike p1 which used sigmoid.

---

## Critical path

```
Fine-tune DistilBERT on Kaggle (PubMed RCT)
  → push model to Ceph RGW
    → FastAPI serving (load from RGW, /predict)
      → Dockerfile + local docker run test
        → Helm chart deploy to K8s
          → Streamlit demo (calls FastAPI)
            → CI/CD pipeline
              → Q4 + Q5 docs
```

---

## Phase 1 — Training

| # | Task | Why |
|---|------|-----|
| 1 | `notebooks/train_pubmed_rct.ipynb` | Kaggle notebook: load dataset from HuggingFace Hub, fine-tune DistilBERT with Trainer API, evaluate on test set, save best checkpoint. Produces `best_model/` directory with model weights + tokenizer. |
| 2 | Evaluate and record metrics | Accuracy, macro F1, per-class F1. These go into the Q4/Q5 docs as evidence of real model performance. Target: accuracy ≥ 85% (baseline DistilBERT without domain tuning). |
| 3 | Push model artifacts to Ceph RGW | `python serving/push_artifacts.py` — uploads model weights + tokenizer to `s3://nlp-models/pubmed-rct/kaggle-001/`. Same RGW bucket pattern as p1. |

**Done when:** `aws s3 ls s3://nlp-models/pubmed-rct/kaggle-001/` shows model files.

---

## Phase 2 — Serving

| # | Task | Why |
|---|------|-----|
| 4 | `serving/main.py` | FastAPI app: loads DistilBERT tokenizer + model from RGW at startup (lifespan pattern). `/predict` accepts text string, tokenises, runs inference, returns label + confidence + latency. Same design principles as p1 (dependency injection, fail fast, no leaky abstraction). |
| 5 | `serving/requirements.txt` | transformers, torch, fastapi, uvicorn, boto3, prometheus-client. Pin versions. |
| 6 | `serving/Dockerfile` | Multi-stage distroless build. HuggingFace models need writable cache dir — set `TRANSFORMERS_CACHE=/tmp/hf_cache`. |
| 7 | Local `docker run` test | Run with env vars pointing at RGW. Confirm `/predict` returns correct class for known sentences before touching K8s. Lesson from p1: test locally first. |

**Done when:** `curl -X POST http://localhost:8000/predict -d '{"text": "..."}' ` returns valid label.

---

## Phase 3 — Streamlit demo

| # | Task | Why |
|---|------|-----|
| 8 | `streamlit/app.py` | UI that calls the FastAPI `/predict` endpoint. User pastes a PubMed abstract (or uses a preset example), app splits it into sentences, classifies each, colour-codes by label. Makes the model tangible for reviewers who won't curl an API. |
| 9 | Add to docker-compose for local dev | `streamlit` service that calls `api` service. One command to run the full demo locally. |

---

## Phase 4 — Helm + K8s + CI/CD

| # | Task | Why |
|---|------|-----|
| 10 | `helm/nlp-inference/` chart | Same structure as p1: deployment, service, configmap, HPA. Two deployments: `nlp-api` and `nlp-streamlit`. Streamlit calls the API via in-cluster service name. |
| 11 | Sealed Secrets for RGW creds | Same `kubeseal` pattern as p1. |
| 12 | GitHub Actions CI | pytest → docker build × 2 (api + streamlit) → push GHCR → update values.yaml tags. |
| 13 | ArgoCD Application CR | Watches `helm/nlp-inference/` on main branch. |

---

## Phase 5 — Tests + Docs

| # | Task | Why |
|---|------|-----|
| 14 | `tests/test_nlp_inference.py` | Unit tests for preprocessing (tokenisation), inference output shape, label mapping. Integration test: mock model returns expected tensor shape → confirm label extraction logic. |
| 15 | `docs/q4-personal-abilities.md` | What this project demonstrates about independent ML capability: dataset choice, training decisions (DistilBERT over BERT, why), evaluation methodology, deployment end-to-end without a template. |
| 16 | `docs/q5-nlp-deploy.md` | Deployment walkthrough: how NLP serving differs from image classification (tokeniser pipeline, variable-length input, batching considerations, model size vs p1). Same GitOps pattern, different model characteristics. |

---

## Acceptance criteria (project complete)

- [ ] Model accuracy ≥ 85% on PubMed RCT test set
- [ ] FastAPI `/predict` returns correct labels in docker run test
- [ ] Streamlit demo classifies a real abstract correctly
- [ ] Deployed to K8s homelab via ArgoCD
- [ ] CI passes (tests + build + push)
- [ ] Q4 and Q5 docs written with real metrics
