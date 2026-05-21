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

Given a sentence from a medical abstract, classify it:

```
"Patients were randomised 1:1 to receive either drug A or placebo."
→ Methods  (0.97)
```

PubMed 200k RCT is a standard benchmark (Dernoncourt & Lee 2017). DistilBERT is 40% smaller than BERT-base with ~97% of its performance — the correct choice for CPU serving.

## Related

- **[p8](../p8-model-registry/)** — exports DistilBERT to ONNX and benchmarks serving formats
- **[p6](../p6-research-agent/)** — uses PubMed as a live data source for the research agent
