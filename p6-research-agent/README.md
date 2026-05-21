# p6 — Research Agent

A LangGraph agent that answers life science research questions by autonomously searching PubMed, looking up proteins in UniProt, and synthesising answers with citations — all from a Streamlit UI backed by a FastAPI service running on Kubernetes.

## What it demonstrates

- LLM agent architecture: LangGraph state graph with reason → act → respond loop
- Tool-augmented generation: structured tool calls with provenance tracking
- Citation hallucination detection: every cited identifier is verified against retrieved tool results
- Production deployment: FastAPI + Streamlit + Ollama (Llama 3.1 8B) on Kubernetes

## Stack

| Component | Choice |
|-----------|--------|
| LLM | Llama 3.1 8B via Ollama (local, no API key) |
| Agent framework | LangGraph |
| Tools | PubMed E-utilities, UniProt REST API, ChromaDB RAG |
| API | FastAPI with citation extraction and hallucination check |
| UI | Streamlit with collapsible agent trace |
| Orchestration | Helm chart, ArgoCD GitOps |

## Example query

> *"What proteins interact with TP53 in the DNA damage response?"*

The agent:
1. Searches PubMed for recent papers on TP53 and DNA damage
2. Fetches abstracts for the most relevant results
3. Looks up TP53 in UniProt (accession P04637) for canonical protein data
4. Synthesises an answer citing only retrieved identifiers

## Key design decisions

- **Minimum tool calls rule** — the system prompt requires `pubmed_fetch` before citing any PMID; titles from `pubmed_search` alone are not sufficient
- **Citation provenance validation** — every `[PMID:xxxxx]` and `[UniProt:Pxxxxx]` in the answer is checked against the retrieved identifier set; unverified citations surface a warning
- **English-only filter** — PubMed searches are wrapped with `AND English[Language]`

See [`docs/how-it-works.md`](docs/how-it-works.md) for the full architecture, and [`docs/design-decisions.md`](docs/design-decisions.md) for post-deployment fixes.

## Related

- **[p7](../p7-rag-evaluation/)** — evaluates and extends the RAG component used by this agent
- **[p9](../p9-knowledge-graph/)** — structured alternative to RAG for relationship queries
