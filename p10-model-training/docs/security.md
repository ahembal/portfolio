# Security & Data Handling
*p10 — Model Training & Benchmarking*

---

## Training data

### BEETLE dataset terms

The BEETLE training data is distributed by Grand Challenge under the challenge's
data use agreement. Key constraints:

- **Non-commercial use only** — the dataset may not be used for commercial
  purposes without explicit permission from the challenge organisers.
- **No redistribution** — the raw WSIs and annotations must not be shared
  publicly or with third parties.
- **Derived artefacts** — tiles extracted by `data/pipeline.py` are derived
  from the dataset and are subject to the same restrictions.

Practical implication: `data/raw/` and `data/tiles/` are gitignored. They
must never be committed to the repository. The `.gitignore` at the repo root
already excludes `data/raw/` and `data/tiles/`.

### Patient data

WSIs are clinical specimens from breast cancer patients. Even de-identified WSIs
carry re-identification risk at scale (slide appearance can be correlated with
institutional staining protocols). The tiles extracted by the pipeline are
sufficiently cropped that individual tile re-identification is not a realistic
concern, but the raw WSIs must be treated as sensitive.

Storage: keep BEETLE WSIs on Dardel scratch (NOBACKUP partition) — they are
not backed up, which aligns with SNIC data handling expectations for clinical
datasets. Do not store on personal laptops or cloud storage without explicit
data governance approval.

---

## Model weights

Trained model weights are stored in RGW (Ceph object storage on the homelab
cluster) via the p8 registry. Weights are not patient data — they are numerical
parameters derived from aggregated statistics — but they are subject to the
dataset's non-commercial use restriction.

Weights are not committed to git. The p8 registry stores the RGW path and
SHA-256 checksum; weights are downloaded at inference time by the submission
container.

---

## Grand Challenge submission container

The submission Docker image contains:
- Trained model weights (COPY into image at build time)
- `src/infer.py` and its dependencies
- No training code, no BEETLE dataset files

### Build-time considerations

The weights file embedded in the image is accessible to anyone with access to
the Docker image. The image is submitted to Grand Challenge's private registry
(not Docker Hub). Do not push the submission image to a public registry.

### Runtime isolation

Grand Challenge runs submission containers in an isolated environment:
- No outbound network access during inference
- Input WSI mounted read-only at a fixed path
- Output directory mounted writable at a fixed path
- Time limit per slide (challenge-specific)

The inference code must not attempt network calls (no model downloads, no
external API calls). All weights must be in the image.

### Container security posture

The submission container should follow minimal-image principles:
- Base image: `python:3.11-slim` or a minimal CUDA image — not a full Ubuntu
- No SSH server, no dev tools, no compilers in the final image
- Run as non-root: `USER inference` in the Dockerfile
- Dependencies pinned to exact versions (reproducibility + no silent upgrades)

---

## Foundation model weights (UNI, CONCH)

UNI and CONCH require gated HuggingFace model access (academic non-commercial
agreement). The weights must not be redistributed.

When embedded in the submission container:
- The gated weights are inside a private Docker image — acceptable under the
  terms of the HuggingFace agreement (no public redistribution)
- Do not push a submission image containing UNI/CONCH weights to a public
  registry

---

## EU AI Act classification

A segmentation model used to support diagnostic decisions in breast cancer
pathology falls under the EU AI Act **high-risk** category (Annex III, point 5a:
AI systems intended to be used as safety components in the management or
operation of critical digital infrastructure, or in medical devices).

Specifically, systems intended for use as a **medical device** fall under MDR
(Medical Device Regulation 2017/745). A CE marking process would be required
for clinical deployment.

**Scope of p10:** This is a research/benchmarking project. The model is
submitted to an academic challenge (BEETLE), not deployed in a clinical
workflow. It does not constitute a medical device in its current form.

If any outputs of p10 were to be used in a clinical decision support context:
- A clinical evaluation under MDR Annex XIV would be required
- ISO 14971 risk management process would apply
- IEC 62304 software lifecycle standard would apply
- Reporting under CLAIM 2024 and TRIPOD+AI would be expected

This is documented here for awareness, not compliance — p10 does not require
regulatory action in its current scope.
