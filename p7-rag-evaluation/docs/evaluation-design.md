# Evaluation Design
*p7 — RAG Evaluation & Hybrid Retrieval*

---

## The history — from token overlap to LLM-as-judge

Before LLMs were cheap enough to use as evaluators, NLP systems were scored
by counting word overlap between the generated output and a reference answer.
Two metrics dominated:

**BLEU** (Bilingual Evaluation Understudy, 2002) — originally designed for
machine translation. Counts how many n-grams (word sequences of length 1–4)
from the generated translation appear in the human reference translation. Still
reported in most translation benchmarks because it allows comparison with
papers going back 20 years.

**ROUGE** (Recall-Oriented Understudy for Gisting Evaluation, 2004) — designed
for text summarisation. Counts overlapping words or phrases between a generated
summary and a reference. ROUGE-1 counts single words; ROUGE-L counts the
longest common subsequence.

Both are fast, deterministic, and require no LLM. That was their appeal.

**The problem:** they measure surface-level word similarity, not meaning.

```
Reference:  "The subject was deceased."
Generated:  "The patient died."
ROUGE score: 0   ← no words overlap
```

Both sentences say the same thing. ROUGE says the generated answer is completely
wrong. This is not a corner case — in biomedical text, synonyms, abbreviations,
and paraphrasing are the norm (TP53 / p53 / P04637 / tumour suppressor protein).

A system that always uses the exact words of its training data scores high on
BLEU/ROUGE. A system that paraphrases correctly scores low. BLEU/ROUGE reward
memorisation, not understanding.

**Why they are still used:** academic reproducibility. A BLEU score from 2024
can be compared directly to a BLEU score from 2005. LLM-as-judge scores cannot
be compared across papers because different judge models produce different scores.

**Why p7 uses LLM-as-judge instead:** the task is not translation or
summarisation — it is answering biomedical questions. Correctness requires
understanding meaning, not counting words. LLM-as-judge is less reproducible
across judge models but far more accurate at measuring what actually matters.

---

## Why LLM-as-judge

Evaluating a RAG system without labelled data requires an automated judge.
Manual evaluation is too slow at scale — a 50-question benchmark run after
every retrieval change is not feasible by hand.

The LLM-as-judge approach asks a language model to score each
query-retrieval-answer triple on defined criteria. It is not ground truth,
but it is a consistent, reproducible signal that tracks relative improvement.

---

## Self-evaluation bias

A well-known failure mode: if the same model generates the answer *and* judges
it, scores are inflated. The model tends to score its own outputs higher because:

- It recognises its own phrasing and style as "correct"
- It filled gaps in the retrieved context during generation; the judge sees
  a fluent answer and doesn't notice the gap that was silently papered over
- The judge and generator share the same knowledge biases

This is documented in the MT-Bench paper (Zheng et al. 2023), which showed
GPT-4 systematically preferred GPT-4-generated answers over equally good human
answers when used as a judge.

**What this means in practice:** the generator and judge should be different
systems. In p7:
- The **generator** is the p6 research agent — a separate service with its
  own tool-calling pipeline, system prompt, and Ollama instance
- The **judge** is a standalone LLM call with a scoring prompt

When running without the p6 agent (e.g. in CI), the inline fallback generator
uses the same model as the judge — this is documented as a limitation in
`src/evaluation/runner.py`. The scores from the inline fallback are useful for
tracking relative changes but should not be compared to scores produced with
the real agent.

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
