# Trust Model
*p8 — Model Registry*

---

## The core question

> If this model produces a wrong prediction, can I prove what it did and why?

This document explains how the registry answers that question — what integrity
mechanisms are used, how they work per source type, and where the gaps are.

---

## SHA strategy by source type

Different model sources have different native integrity mechanisms.
Using the platform's own mechanism is more reliable than reimplementing it.

### HuggingFace Hub — commit hash

HuggingFace tracks model versions via Git commit hashes. Every push to a model
repo produces a new commit SHA. The registry stores this commit hash as `sha`.

```
sha: 8b027eeb8f7c0490f4cc30f43ca03ce3b0fe2ec4
```

**How to compute:**
```bash
python src/verify.py --compute resnet18-tiatoolbox-pcam v1
```

**How to verify:**
```bash
python src/verify.py resnet18-tiatoolbox-pcam v1
```

`verify.py` calls the HuggingFace API and compares the current commit hash
against the registered one. If the model maintainer pushes new weights, the
hash changes and verification fails — alerting you to review the change before
deploying.

### Ceph RGW (S3) — SHA-256

For models stored in our own RGW, there is no platform-provided integrity hash.
We compute SHA-256 of the weights file directly.

```
sha: 85a297c5e4046c3d387167166ad3056e5356a22ad872255a3f4942416355ea42
```

**How to compute:**
```bash
source .env
RGW_ENDPOINT=http://<quick-thrush-ip> \
RGW_ACCESS_KEY=$RGW_ACCESS_KEY \
RGW_SECRET_KEY=$RGW_SECRET_KEY \
python src/verify.py --compute distilbert-pubmed-rct v1
```

**How to verify:**
```bash
# same command without --compute
python src/verify.py distilbert-pubmed-rct v1
```

`verify.py` downloads the file from RGW and recomputes the SHA-256.
A mismatch means the file in RGW was modified after registration.

---

## The governance gate

No model can be deployed without:

1. A registry entry with a verified `sha` (not `UNVERIFIED`)
2. A linked `evaluation_id` pointing to a completed evaluation

`validate.py` enforces both. Run it before every deployment:

```bash
python src/validate.py
```

`cli.py audit` shows the current trust status of all entries:

```bash
python src/cli.py audit
```

---

## What is not covered

**Pretrained model training provenance** — we trust that TIAToolbox trained their
model as described in Pocock et al. 2022. We cannot verify their training process.
The commit hash verifies the weights haven't changed since we registered them —
it does not verify they were produced by the described training run.

**Runtime integrity** — once the model is loaded into the serving container,
we don't verify it again per request. A production system would use TPM or
secure enclave mechanisms for runtime integrity. Out of scope here.

**Approval workflow** — any contributor can register a model and create a
deployment entry. A production system needs PR-based approval with defined
reviewers. Currently enforced by convention, not tooling.

---

## Current registry trust status

Run `python src/cli.py audit` for the live status.

As of 2026-05-12:
- `resnet18-tiatoolbox-pcam v1` — ✓ HuggingFace commit hash verified
- `distilbert-pubmed-rct v1` — ✓ RGW SHA-256 verified
- `pcam-kaggle-001` experiment — ✓ RGW SHA-256 verified
- `pcam-tiatoolbox-v1-eval-001` — ⚠ partial evaluation (metrics from paper, not our own run)
