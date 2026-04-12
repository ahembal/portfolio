# Project 1 — PCam ML Deployment Pipeline
## Progress Tracker
*Last updated: 2026-04-12*

---

## Steps

| # | Step | Status | Notes |
|---|------|--------|-------|
| 1 | Train on Kaggle (T4 GPU) | 🟡 Running | 5 epochs, ResNet-18, 262k samples |
| 2 | Download artifacts from Kaggle | ⬜ Pending | best_model.pt, metrics.json, config.json |
| 3 | Push artifacts to Ceph RGW | ⬜ Pending | `push_kaggle_artifacts.py --zip ... --run-id kaggle-001` |
| 4 | Write Dockerfile | ⬜ Pending | Multi-stage, pulls model from RGW at startup |
| 5 | Write Helm chart | ⬜ Pending | deployment, service, configmap, hpa |
| 6 | Deploy to K8s on turtle | ⬜ Pending | sought-perch + quick-thrush workers |
| 7 | Test /predict endpoint | ⬜ Pending | curl a real PCam patch image |
| 8 | Load test + HPA demo | ⬜ Pending | locust, kubectl get hpa -w |
| 9 | Write Q5, Q7, Q9 docs | ⬜ Pending | Answer application questions |

---

## Files created

| File | Purpose |
|------|---------|
| `train/train.py` | Training script — ResNet-18, dependency injection, full metrics |
| `train/kaggle_train.ipynb` | Kaggle notebook — plan B compute (T4 GPU) |
| `train/submit_dardel.sh` | SLURM submit script for PDC Dardel (plan A) |
| `train/push_artifacts.py` | Push artifacts from Dardel → Ceph RGW |
| `train/push_kaggle_artifacts.py` | Push downloaded Kaggle zip → Ceph RGW |
| `serving/main.py` | FastAPI inference service — loads model from RGW |
| `serving/requirements.txt` | Serving dependencies |
| `serving/Dockerfile` | ⬜ Not written yet |
| `helm/pcam-inference/` | ⬜ Not written yet |
| `pyproject.toml` | Project packaging + dev tools |
| `requirements.txt` | Pinned deps via pip-compile |

---

## Infrastructure used

| Layer | System | Details |
|-------|--------|---------|
| Compute | Kaggle T4 GPU | Plan B — swappable for Dardel later |
| Storage | Ceph RGW on turtle | `http://192.168.1.16`, bucket: `ml-artifacts` |
| Serving | K8s on turtle | sought-perch + quick-thrush workers |

---

## Answers targeted

| Question | How this project answers it |
|----------|-----------------------------|
| Q5 | Train (Kaggle/Dardel) → evaluate (AUC, F1, confusion matrix) → deploy (Docker + Helm + K8s) |
| Q7 | Real Helm chart, real K8s cluster, multi-stage Dockerfile |
| Q9 | Written reflection on K8s friction for ML (step 9) |

---

## Kaggle run details

- Dataset: `andrewmvd/metastatic-tissue-classification-patchcamelyon`
- Model: ResNet-18, ImageNet pretrained
- Epochs: 5
- Batch size: 128
- Optimizer: Adam, lr=1e-4
- First step loss: 0.7737

## Results (fill in after training)

| Epoch | Train loss | Val loss | Accuracy | AUC | F1 |
|-------|------------|----------|----------|-----|----|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
