# Evaluation Design
*p7 — RAG Evaluation & Hybrid Retrieval*

---

## Why LLM-as-judge

Evaluating a RAG system without labelled data requires an automated judge.
Manual evaluation is too slow at scale — a 50-question benchmark run after
every retrieval change is not feasible by hand.

The LLM-as-judge approach asks a language model to score each
query-retrieval-answer triple on defined criteria. It is not ground truth,
but it is a consistent, reproducible signal that tracks relative improvement.

---

## The three core metrics

These are the de facto standard metrics for RAG evaluation, used by RAGAS,
TruLens, and most production RAG systems:

| Metric | What it measures | Input |
|--------|-----------------|-------|
| Context relevance | Are the retrieved chunks relevant to the question? | query + chunks |
| Faithfulness | Does the answer contain only claims supported by the chunks? | query + chunks + answer |
| Answer relevance | Does the answer address what was asked? | query + answer |

Together they cover the two failure modes of RAG:
- **Retrieval failure** — wrong chunks retrieved (context relevance catches this)
- **Generation failure** — answer doesn't follow from the chunks (faithfulness), or doesn't answer the question (answer relevance)

---

## Frameworks comparison

### RAGAS
- **What:** Open source Python library. Defines context relevance, faithfulness, answer relevance as core metrics. Also includes context recall and context precision if ground-truth answers are available.
- **Judge model:** Any LLM via LangChain — defaults to OpenAI but works with Ollama.
- **Strengths:** Most widely used, good documentation, active community.
- **Weaknesses:** Requires LangChain integration. Some metrics need ground-truth answers.
- **Repo:** `explodinggradients/ragas`

### TruLens
- **What:** Evaluation and tracing framework from TruEra. Similar three-metric approach plus custom feedback functions.
- **Judge model:** OpenAI or any LLM via their abstraction layer.
- **Strengths:** Built-in dashboard, supports tracing LLM calls end-to-end.
- **Weaknesses:** More complex setup, dashboard requires running a server.
- **Repo:** `truera/trulens`

### ARES (Stanford)
- **What:** Academic framework that trains a small judge model on synthetic data rather than prompting a large LLM.
- **Judge model:** Fine-tuned DeBERTa — much cheaper to run than GPT-4 at scale.
- **Strengths:** Cheaper per query, more consistent scores, doesn't depend on a large LLM.
- **Weaknesses:** Requires generating synthetic training data upfront. Less flexible.
- **Paper:** "ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems" (Saad-Falcon et al., 2023)

### DeepEval
- **What:** Open source testing framework for LLM apps. Includes RAG-specific metrics plus hallucination detection, toxicity, bias.
- **Judge model:** OpenAI by default, configurable.
- **Strengths:** pytest integration — RAG evaluation as unit tests. Wide metric coverage.
- **Weaknesses:** Many metrics require OpenAI. Local LLM support is experimental.
- **Repo:** `confident-ai/deepeval`

---

## Comparison table

| | RAGAS | TruLens | ARES | DeepEval | p7 (this project) |
|---|---|---|---|---|---|
| Context relevance | ✅ | ✅ | ✅ | ✅ | ✅ |
| Faithfulness | ✅ | ✅ | ✅ | ✅ | ✅ |
| Answer relevance | ✅ | ✅ | ✅ | ✅ | ✅ |
| Local LLM support | ✅ | Partial | ✅ (trained model) | Experimental | ✅ (Ollama) |
| No API key needed | ✅ | ❌ | ✅ | ❌ | ✅ |
| Ground truth required | Optional | Optional | Yes (synthetic) | Optional | No |
| pytest integration | ❌ | ❌ | ❌ | ✅ | ✅ |
| Dashboard | ❌ | ✅ | ❌ | ✅ | Planned (p7 Phase 4) |

---

## What automated evaluation cannot measure

- **Factual correctness** — the judge scores whether the answer follows from the retrieved chunks, not whether the chunks themselves are correct. A faithfulness score of 1.0 on wrong sources is still wrong.
- **Clinical or safety-critical accuracy** — automated evaluation is not suitable as the sole quality gate for medical, legal, or safety applications.
- **Novelty or insight** — whether the answer adds value beyond what was in the chunks.
- **User satisfaction** — scores do not predict whether a real user would find the answer useful.

---

## Future work — benchmarking frameworks against each other

A natural next step for p7 is to run the same benchmark through RAGAS, TruLens,
and p7's own judge and compare scores. This would:
1. Validate that p7's scores correlate with established frameworks
2. Identify which framework is most consistent on life science queries
3. Measure cost per evaluation (tokens used, latency)

This comparison would make p7 a genuine evaluation research contribution rather
than just a reimplementation.
