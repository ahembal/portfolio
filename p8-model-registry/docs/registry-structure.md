# Registry Structure
*p8 — Model Registry*

---

## The core question

Every design decision in this registry stems from one question:

> **If this model produces a wrong prediction, can I prove what it did and why?**

In histology (p1 PCam), a wrong prediction could mean misdiagnosed cancer.
In any regulated domain, it means liability. The registry exists to make the
answer to that question "yes".

---

## Why four concepts, not one

The naive approach is one YAML file per model with everything in it — architecture,
metrics, deployment info. This fails because it conflates four fundamentally different
things that change at different times, for different reasons, by different people:

```
WHAT    →  models/       — what the model is (immutable once registered)
WHY     →  experiments/  — the training run that produced the weights
PROOF   →  evaluations/  — evidence the model performs as claimed
WHERE   →  deployments/  — where and when it runs (changes over time)
```

Mixing these means:
- A redeployment requires editing the model definition — wrong
- Metrics look like model properties when they're actually evaluation results — misleading
- You can't answer "what changed between v1 and v2?" — no lineage
- No governance gate between evaluation and deployment — dangerous

---

## The four concepts

### models/ — WHAT

Immutable once registered. Describes the model identity: architecture, weights format,
preprocessing requirements, class mapping, and the SHA-256 of the weights file.

**The SHA is not optional.** A model without a verified hash cannot be trusted —
anyone could swap the weights file and the registry would not know.

```
models/
  resnet18-tiatoolbox-pcam-v1.yaml
  distilbert-pubmed-rct-v1.yaml
```

When does a new version get created? Only when the weights or architecture change.
A documentation update does not warrant a new version.

### experiments/ — WHY

Records the training run that produced a set of weights. Required for all
`source: trained` or `source: fine-tuned` models. Captures: who ran it, on what
compute, with what hyperparameters, producing what artifact at what location with
what SHA.

Without experiments, you cannot reproduce a model. Without reproducibility,
you cannot debug failures or improve the model systematically.

```
experiments/
  pcam-kaggle-001.yaml       ← our own PCam training run
  pubmed-rct-kaggle-001.yaml ← our own NLP training run
```

Pretrained third-party models (TIAToolbox, HuggingFace) do not have experiment
entries — their training is documented in their papers and model cards.

### evaluations/ — PROOF

Metrics are not a property of a model. They are the result of running the model on
a specific dataset, at a specific time, by a specific person, with a specific threshold.

AUC 0.96 without a dataset reference is not a proof — it's a number. An evaluation
entry makes the context explicit and permanent.

```
evaluations/
  pcam-tiatoolbox-v1-eval-001.yaml   ← PCam test split, Youden threshold
  pubmed-rct-v1-eval-001.yaml
```

### deployments/ — WHERE

Mutable. Records where a model runs, when it was deployed, and crucially: which
evaluation approved it for deployment. **No deployment is valid without a referenced
evaluation.** This is the governance gate.

```
deployments/
  p1-pcam-inference-prod-001.yaml
  p4-nlp-inference-prod-001.yaml
```

---

## The governance gate

```
Model registered (sha verified)
        │
        ▼
Evaluation run against test set
        │
        ▼
Evaluation entry created with results
        │
        ▼
Deployment entry created — references evaluation_id
        │
        ▼  ONLY NOW
Service deployed
```

A deployment without an `evaluation_id` is rejected by `validate.py`.
This is the minimum viable trust guarantee.

---

## The trust anchor — verify.py

`src/verify.py` downloads the model weights from their registered location and
computes the SHA-256. If it does not match the `sha` field in the model entry,
verification fails and deployment is blocked.

This prevents:
- Accidental weight file corruption
- Silent model substitution
- Deployment of unregistered model versions

---

## What this registry does NOT solve

This is documented honestly because understanding the limits is as important as
understanding the capabilities:

- **No access control** — any contributor can register or modify entries. A
  production system needs approval workflows (PR reviews at minimum, dedicated
  governance tooling at scale).

- **No automated verification in CI** — `verify.py` must be run manually. A
  production system would run it as a CI gate before every deployment.

- **No lineage for pretrained models** — we register what TIAToolbox published
  but we cannot verify their training process. We trust their SHA.

- **YAML does not scale** — at hundreds of models this becomes unwieldy. The
  right long-term solution is MLflow, DVC, or a dedicated metadata store. See
  `docs/why-not-mlflow.md`.

- **No UI** — a CLI (`src/cli.py`) is the interface. Production teams need
  dashboards showing which models are deployed, when evaluations expire, etc.

- **No schema migration path** — if a required field is added or renamed, all
  existing YAML entries must be updated manually. A production system would use
  a schema version field and a migration script. Current approach: bump
  `schemas/*.schema.yaml`, run `python src/validate.py` to find all entries
  that break, and update them before merging. Document the change in a
  `CHANGELOG.md` entry with the affected field names.
