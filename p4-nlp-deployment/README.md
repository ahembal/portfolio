# p4 — NLP Deployment

Five-class sentence classification on PubMed RCT abstracts (Background / Objective / Methods / Results / Conclusions), served with the same production patterns as p1.

## What it demonstrates

- Fine-tuning a transformer (DistilBERT) on a domain-specific NLP task
- Serving a transformer model via FastAPI using the same GitOps pipeline as p1 — showing the pattern is reusable across modalities
- Streamlit demo UI for interactive sentence-level classification of medical abstracts
- ONNX export for transformer models via HuggingFace optimum (benchmarked in p8)

## Stack

| Component | Choice |
|-----------|--------|
| Model | DistilBERT-base-uncased fine-tuned on PubMed 200k RCT |
| Training | HuggingFace Trainer API, Kaggle T4 GPU |
| Serving | FastAPI + Streamlit demo |
| Container | Distroless, non-root — same as p1 |
| Orchestration | Helm chart, ArgoCD GitOps |

## The task

Five-class sentence classification for PubMed RCT abstracts. Each sentence is assigned one of:

| Label | Meaning |
|-------|---------|
| BACKGROUND | Context and motivation for the study |
| OBJECTIVE | Research question or hypothesis |
| METHODS | Study design, interventions, measurements |
| RESULTS | Quantitative findings |
| CONCLUSIONS | Interpretation and clinical implications |

PubMed 200k RCT is a standard benchmark (Dernoncourt & Lee 2017). DistilBERT is 40% smaller than BERT-base with ~97% of its NLP benchmark performance — the right choice for CPU serving where inference latency matters.

## Model metrics

| Metric | Value |
|--------|-------|
| Accuracy | 86.8% |
| Macro F1 | 0.857 |
| Weakest class | OBJECTIVE (F1 0.640) |

Macro F1 is the primary metric because classes are imbalanced and all class errors matter equally. See [`docs/training-design.md`](docs/training-design.md) for evaluation methodology.

## Live endpoint

Running on the homelab cluster at `http://100.82.75.34:30640`.

```bash
curl -X POST http://100.82.75.34:30640/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Patients were randomised to receive either drug A or placebo. The primary endpoint was overall survival."}'
```

Response:
```json
{
  "sentences": [
    {"text": "Patients were randomised to receive either drug A or placebo",
     "label": "METHODS", "confidence": 0.98, "colour": "#27AE60"},
    {"text": "The primary endpoint was overall survival",
     "label": "METHODS", "confidence": 0.96, "colour": "#27AE60"}
  ],
  "latency_ms": 1257.3
}
```

## Run locally

```bash
# Pull and run the serving image
docker run -p 8000:8000 \
  -e RGW_ENDPOINT=http://<rgw-host> \
  -e RGW_ACCESS_KEY=<key> \
  -e RGW_SECRET_KEY=<secret> \
  -e RGW_BUCKET=p4-models \
  -e MODEL_KEY=distilbert-pubmed-rct-v1/ \
  ghcr.io/ahembal/p4-nlp-inference:latest

curl http://localhost:8000/health
```

## Deploy to cluster

```bash
helm upgrade --install p4 helm/nlp-inference/ \
  --set image.tag=<sha>
```

ArgoCD manages the live deployment — see [`helm/nlp-inference/`](helm/nlp-inference/).

## Key design decisions

- **Model loaded from Ceph RGW at startup** — not bundled in the image; a 250 MB model in a distroless image would require rebuilding on every model update
- **HuggingFace cache redirected to `/tmp`** — distroless has no writable paths outside `/tmp`; `TRANSFORMERS_CACHE=/tmp/hf_cache` must be set or HuggingFace raises at import time
- **Macro F1 over accuracy** — OBJECTIVE class is hardest (F1 0.640); accuracy would mask this by rewarding the majority classes

See [`docs/implementation.md`](docs/implementation.md) and [`docs/how-it-works.md`](docs/how-it-works.md) for full detail.

## Related

- **[p8](../p8-model-registry/)** — exports this model to ONNX and benchmarks serving formats
- **[p6](../p6-research-agent/)** — uses PubMed as a live data source for the research agent
