# Implementation Notes — P4 NLP Deployment
*Last updated: 2026-04-28*

This document describes how the project was built: structure chosen, problems hit during development, and decisions made along the way. For how the finished product works see `how-it-works.md`. For training design rationale see `training-design.md`.

---

## notebooks/train_pubmed_rct.ipynb

### Dataset choice
- Initial attempt used pietrolesci/pubmed-200k-rct: 2.27M rows, ~6 hours per epoch on T4 — too slow for iterative development
- Switched to armanc/pubmed-rct20k: ~177k rows, ~45 minutes per 3 epochs on T4 — correct choice
- DatasetNotFoundError on joolsa/pubmed_rct_200k (dataset does not exist) — had to find correct dataset name

### Training setup
- Model: distilbert-base-uncased, fine-tuned for sequence classification (5 labels)
- Labels: BACKGROUND, METHODS, RESULTS, CONCLUSIONS, OBJECTIVE (strings, not ints — DatasetDict uses string labels)
- Tokenizer: processing_class= parameter (not tokenizer=) — HuggingFace Trainer API changed in transformers>=4.47
- 3 epochs, batch_size=32, T4 GPU, ~45 min total

### Kaggle dependency issues fixed
- boto3==1.34.0 pinned → broke aiobotocore 3.3.0 (needs botocore>=1.42.62,<1.42.71). Fixed: removed boto3 pin (Kaggle has a compatible version pre-installed)
- transformers==4.40.0 pinned → Kaggle's sentence-transformers 5.2.3 requires >=4.41.0. Fixed: pin to >=4.41.0
- datasets==2.19.0 → installed fsspec==2024.3.1, conflicted with Kaggle's s3fs and gcsfs. Fixed: unpinned datasets

### Model upload
- RGW upload from Kaggle failed: Kaggle runs in Google Cloud, Tailscale IP (192.168.x.x) not routable externally
- Workaround: push to HuggingFace Hub from Kaggle → pull to laptop → push to RGW (s3://nlp-models/pubmed-rct/v1/)
- HF token stored in pass homelab/huggingface/kaggle-token

### Results
- accuracy=86.8%, macro F1=0.806
- Per-class F1: METHODS=0.937, RESULTS=0.915, CONCLUSIONS=0.833, BACKGROUND=0.706, OBJECTIVE=0.640
- Within expected DistilBERT range (86-88% on PubMed RCT)
