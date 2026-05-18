# Text model benchmarking

How the DistilBERT benchmark works and why it differs from the vision benchmark.

---

## Why text models need a model directory

The vision benchmark (ResNet-18) pulls the model directly from HuggingFace Hub
with a single call:

```python
timm.create_model("hf-hub:org/model", pretrained=True)
```

This works because the Hub stores the full model: architecture definition,
weights, and preprocessing config all in one place.

The NLP model (DistilBERT) is stored differently. Only the fine-tuned weights
(`model.safetensors`) are in RGW. The config and tokenizer are not stored there
because they are identical to the base `distilbert-base-uncased` model on
HuggingFace Hub — except for two fields that were changed during fine-tuning:
`num_labels` (2 → 5) and `id2label` / `label2id` (the class names).

`transformers.AutoModelForSequenceClassification.from_pretrained()` requires a
directory containing all three:

```
model_dir/
├── config.json          ← architecture + num_labels + class names
├── tokenizer.json       ← how to convert text → token IDs
├── tokenizer_config.json
├── vocab.txt
└── model.safetensors    ← fine-tuned weights
```

If you pass only the weights, `transformers` raises a `ValueError` because it
cannot determine the output shape. If you pass the base model's unpatched
`config.json`, PyTorch raises a shape mismatch error when loading the weights
because the base config expects a 2-class head and the fine-tuned weights have
a 5-class head.

`_build_model_dir` assembles this directory in a temp location before each
benchmark run:

1. Download `config.json` from `distilbert-base-uncased` on HuggingFace Hub
2. Patch `num_labels`, `id2label`, `label2id` to match the fine-tuned head
3. Copy tokenizer files from the base model (fine-tuning does not change these)
4. Download `model.safetensors` from RGW

The resulting directory is what both the PyTorch and ONNX benchmark paths load
from.

---

## Why uncased

`distilbert-base-uncased` lowercases all text before tokenisation. "The" and
"the" become the same token. The alternative — `distilbert-base-cased` —
preserves capitalisation.

Uncased is the right choice for PubMed RCT sentence classification because the
task (predicting background / objective / method / result / conclusion) is
determined by the meaning and position of the sentence in the abstract, not by
capitalisation. All sentences start with a capital by convention, so
sentence-initial capitalisation is a uniform signal across all five classes —
it carries no discriminative information. Mid-sentence capitalisation (proper
nouns, acronyms) does not change which class a sentence belongs to.

---

## RGW credentials

The benchmark job reads RGW credentials from environment variables:

| Variable | Description |
|----------|-------------|
| `RGW_ENDPOINT` | Ceph RGW HTTP endpoint |
| `RGW_ACCESS_KEY` | S3 access key |
| `RGW_SECRET_KEY` | S3 secret key |

These are injected at runtime from a Kubernetes Secret
(`p8-benchmark-rgw-credentials`). Create it before deploying the job:

```
kubectl create secret generic p8-benchmark-rgw-credentials \
  --from-literal=endpoint=http://<rgw-ip> \
  --from-literal=access-key=<KEY> \
  --from-literal=secret-key=<SECRET>
```

The vision benchmark (ResNet-18) does not need these — it pulls from
HuggingFace Hub. The env vars are marked `optional: true` in the Job spec so
the PCam job still runs without the secret.
