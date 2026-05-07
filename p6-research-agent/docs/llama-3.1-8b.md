# How Llama 3.1 8B Works
*Last updated: 2026-05-06*

Llama 3.1 8B is a large language model developed by Meta AI and released as
open weights. This document explains what it is, how it generates text, how
tool-calling works, and why it is used in p6.

---

## Data flow — from question to answer

```
User question: "What is known about TP53 in glioblastoma?"
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Tokeniser                                       │
│  "What is known..." → [1724, 318, 1900, 546, …] │
│  (one integer per word fragment)                 │
└─────────────────────────────────────────────────┘
        │  token IDs + tool schemas
        ▼
┌─────────────────────────────────────────────────┐
│  Transformer — 32 attention layers               │
│                                                  │
│  Reads all tokens in context window.             │
│  Each layer asks: which earlier tokens           │
│  are relevant to predicting the next one?        │
│                                                  │
│  Output: probability over 128k possible          │
│  next tokens — OR a structured tool_call block   │
└─────────────────────────────────────────────────┘
        │
        ├── if tool call requested ──────────────────────────────────────┐
        │                                                                 │
        │   {"tool_calls": [{"name": "pubmed_search",                    │
        │                    "arguments": {"query": "TP53 glioblastoma"}}]}
        │                                                                 │
        │                          ▼                                     │
        │                  LangGraph executes tool                       │
        │                  (real HTTP call to NCBI)                      │
        │                          │                                     │
        │                  tool result appended to context               │
        │                          │                                     │
        └──────────────────────────┘ ← model called again with result   │
                                                                         │
        └── if no tool call → generate final answer token by token ──────┘
                │
                ▼
        ┌───────────────────────┐
        │  De-tokeniser         │
        │  [1234, 5678, …]      │
        │  → "TP53 mutations…"  │
        └───────────────────────┘
                │
                ▼
        Final answer with citations
```

---

## What kind of model is it?

Llama 3.1 8B is a **transformer decoder** — the same class of model as GPT-4,
Claude, and Gemini, but smaller and open-weight (the parameters are publicly
downloadable).

"8B" means 8 billion parameters — numerical weights learned during training on
large amounts of text. These weights encode statistical patterns about language:
what words tend to follow what other words, how sentences are structured, and
factual associations from the training data.

---

## How it generates text

```
Context so far: "TP53 is a tumour"
        │
        ▼
  Model predicts next token:
  "suppressor" → 42%
  "protein"    → 31%
  "gene"       → 18%
  …
        │  sample
        ▼
  Append "suppressor" to context
        │
        ▼
Context: "TP53 is a tumour suppressor"
        │
        └──► repeat until [STOP] token
```

The model generates text **one token at a time**, left to right. A token is
roughly a word fragment (e.g. "glio" and "blastoma" are two separate tokens).

For each new token, the model:
1. Reads all previous tokens in the context window
2. Computes attention — which earlier tokens are most relevant to what comes next
3. Outputs a probability distribution over the entire vocabulary (~128k tokens)
4. Samples the next token from that distribution

This repeats until the model generates a stop token or reaches the context limit.
The full context window for Llama 3.1 8B is 128k tokens — large enough to hold
several long research papers.

This is why inference is slow on CPU: for each token, the model performs a
forward pass through all 32 transformer layers, each involving large matrix
multiplications. On a T4 GPU this takes ~10ms per token. On CPU it takes ~100ms.
A 200-token answer takes 20 seconds on CPU.

---

## How tool-calling works

Llama 3.1 8B was fine-tuned to understand structured tool-call syntax. When
tool schemas are provided (as JSON), the model can output a structured
`tool_calls` block instead of plain text:

```json
{
  "tool_calls": [{
    "name": "pubmed_search",
    "arguments": {"query": "TP53 glioblastoma", "max_results": 5}
  }]
}
```

LangGraph detects this structure, executes the tool, appends the result to the
message history, and calls the model again. The model sees the tool result and
decides: call another tool, or generate the final answer.

This is not magic — the model learned from training examples where tool outputs
followed tool calls. It is pattern matching, not genuine reasoning. This is why
it sometimes stops too early (matches the "I have enough information" pattern
after one tool call) or hallucinates citations (matches the "cite a paper"
pattern from memory rather than from retrieved content).

---

## Why 8B and not a larger model?

| Model | Parameters | Quality | RAM needed | Inference (CPU) |
|-------|-----------|---------|-----------|-----------------|
| Llama 3.1 8B | 8B | Good | ~16 GB | ~40-60s/query |
| Llama 3.1 70B | 70B | Very good | ~140 GB | Hours/query |
| GPT-4 | ~1T (est.) | Excellent | API only | ~5s/query (API) |

8B fits in the 64 GB RAM on `quick-thrush` with headroom for the OS and other
services. 70B would not fit. GPT-4 would require sending research queries to
an external API — not suitable for a self-contained research tool.

For the portfolio use case (demos, occasional queries) the 8B quality is
acceptable. For production research assistance at scale, a larger model or
API access would be needed.

---

## How Ollama serves it

Ollama is a local model server — it:
1. Downloads and stores the model weights in a quantised format (4-bit or 8-bit
   quantisation reduces 8B float32 weights from ~32 GB to ~4-8 GB)
2. Exposes a REST API at `http://localhost:11434`
3. Manages model loading/unloading from RAM
4. Handles batching and streaming

The p6 API calls Ollama via `langchain-ollama`. The model stays loaded in RAM
between requests — the first request is slow (model load ~10s), subsequent
requests are faster (~40s inference only).

---

## Quantisation

The model is stored in 4-bit quantised format (~4.9 GB). Quantisation reduces
precision — weights are stored as 4-bit integers instead of 32-bit floats.
This reduces memory 8× at a small quality cost (~1-3% on benchmarks).

Without quantisation the 8B model would require ~32 GB RAM. With 4-bit
quantisation it fits in ~5 GB, leaving the rest of `quick-thrush`'s 64 GB
for the OS, Kubernetes, and other workloads.

---

## Limitations relevant to p6

| Limitation | Cause |
|-----------|-------|
| Stops after one tool call | Tool-calling fine-tuning is imperfect — the model pattern-matches "done" too early |
| Hallucinates citations | Training data contained papers cited without retrieval — the model learned to generate citation patterns |
| Non-deterministic | Temperature > 0 means different runs produce different outputs |
| No memory between sessions | Context window resets each query — the model has no memory of previous conversations |
| 128k token limit | Very long research sessions (many tool calls, long abstracts) can exceed the context window |
