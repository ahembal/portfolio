# P6 — Life Science Research Agent — Spec

> Last updated: 2026-04-21

## What this project is

A multi-tool AI agent that helps researchers answer questions that require querying and
synthesising information across multiple life science data sources — literature, protein
databases, and a local document corpus. The agent decides which tools to call, chains
them when needed, and returns a grounded answer with citations.

**Example queries the agent handles:**
- "What is known about TP53 mutations in glioblastoma? Summarise recent papers and
  include the canonical protein domains."
- "Find clinical trials involving PD-L1 inhibitors published after 2023."
- "Given this abstract, which HGNC gene symbols are mentioned and what are their
  known disease associations?"

**Why this design?**
Narrow models (like p1 and p4) answer one well-defined question. Research workflows
rarely work that way — a single question requires literature retrieval, structured
database lookup, and synthesis. The agent architecture handles this naturally:
each data source becomes a tool, the LLM decides how to combine them, and the
system is extensible by adding tools rather than retraining.

**FAIR data note:**
The agent works well precisely *because* the underlying data sources are FAIR.
PubMed records have stable identifiers (PMIDs), machine-readable abstracts, and
structured metadata. UniProt entries are uniquely identified (accession numbers),
interoperable (standard data model across species), and openly accessible via REST.
The agent's grounding and citation ability depends entirely on these properties —
this is a concrete demonstration of why FAIR data infrastructure matters for AI.

---

## Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Agent framework | LangGraph (LangChain) | Graph-based agent: explicit control flow, easy to add tools, observable step-by-step reasoning. LangGraph over plain LangChain because it makes the agent loop explicit rather than hidden in a ReAct string parser. |
| LLM backbone | Llama 3.1 8B via Ollama (local) | Runs on the homelab cluster (CPU inference, ~10 s/query — acceptable for research assistant use). No API key, no cost, no data leaving the network. Can swap to GPT-4o or Claude via a config flag. |
| Embeddings + vector store | sentence-transformers + ChromaDB | Local RAG over a small life science document corpus (e.g., SciLifeLab platform descriptions, PubMed abstracts). ChromaDB persists to disk, no external dependency. |
| Tool: PubMed | Biopython Entrez API | Search and fetch abstracts by query or PMID. NCBI Entrez is the standard programmatic interface to PubMed — rate-limited, no auth required. |
| Tool: UniProt | UniProt REST API | Look up protein by name, gene symbol, or accession. Returns canonical sequence, domains, disease associations, organism. Free, well-documented, stable identifiers. |
| Tool: vector store | ChromaDB (local) | RAG retrieval over the local corpus. When PubMed/UniProt don't have enough context, the agent falls back to the local store. |
| Serving | FastAPI | `/query` endpoint accepts a research question, streams agent steps back, returns final answer + citations. Same design principles as p1 and p4. |
| Demo UI | Streamlit | Chat interface showing the agent's reasoning steps (which tools were called, what they returned) alongside the final answer. Transparency in the reasoning process. |
| Deployment | Helm + K8s (homelab) | Same GitOps pattern as p1/p4. Ollama runs as a sidecar or separate deployment. |

---

## Agent architecture

```
User query
    │
    ▼
LangGraph agent (ReAct loop)
    │
    ├── Tool: pubmed_search(query) → list of abstracts + PMIDs
    ├── Tool: pubmed_fetch(pmid)   → full abstract + metadata
    ├── Tool: uniprot_lookup(gene) → protein record (domains, disease)
    └── Tool: rag_search(query)   → relevant chunks from local corpus
    │
    ▼
LLM synthesises results → answer with inline citations [PMID:12345678]
    │
    ▼
FastAPI response: { answer, citations: [{pmid, title, url}], steps: [...] }
```

The graph has three node types:
- **Reason**: LLM decides which tool(s) to call based on current state
- **Act**: tool is called, result added to state
- **Respond**: LLM generates final answer when it has enough context

This is explicit and inspectable — every tool call and its result are logged
and returned in the `steps` field of the response.

---

## Critical path

```
Ollama running locally with Llama 3.1 8B
  → PubMed tool works (search + fetch)
    → UniProt tool works (gene lookup)
      → LangGraph agent chains the tools correctly
        → FastAPI /query endpoint returns grounded answer
          → RAG corpus indexed in ChromaDB
            → Streamlit chat UI
              → Helm chart deploy to K8s
                → CI/CD
                  → docs
```

---

## Phase 1 — Tools (independent of agent)

| # | Task | Why |
|---|------|-----|
| 1 | `src/tools/pubmed.py` | PubMed search and fetch via Biopython Entrez. `search(query, max_results)` returns list of PMIDs. `fetch(pmid)` returns title, abstract, authors, journal, year. Tested independently before wiring into the agent — tool bugs are much easier to debug in isolation. |
| 2 | `src/tools/uniprot.py` | UniProt REST API wrapper. `lookup(gene_symbol, organism="human")` returns accession, protein name, gene names, domains, disease associations, sequence length. UniProt accessions are stable identifiers — a citation to `P04637` (TP53) is unambiguous and persistent. |
| 3 | `src/tools/vector_store.py` | ChromaDB wrapper: `index(documents)` and `search(query, k)`. Documents are chunked and embedded with `sentence-transformers/all-MiniLM-L6-v2`. Local RAG over a seed corpus (SciLifeLab platform docs + a few hundred PubMed abstracts). Gives the agent grounding beyond live API calls. |
| 4 | `tests/test_tools.py` | Unit tests for each tool with mocked HTTP responses. Confirms parsing logic, error handling (rate limits, 404s), and output schema. Tools are pure functions — easy to test without the agent. |

**Done when:** Each tool can be called directly in a Python shell and returns expected structured output.

---

## Phase 2 — Agent graph

| # | Task | Why |
|---|------|-----|
| 5 | `src/agent/graph.py` | LangGraph graph: nodes (reason, act, respond), edges, state schema. The graph makes the agent's control flow explicit — you can visualise it, unit-test individual nodes, and add new tools without touching the core loop. |
| 6 | `src/agent/prompts.py` | System prompt and tool-use instructions. The system prompt establishes the agent's role (research assistant, cite sources, admit uncertainty), output format (inline PMIDs), and when to stop (when the question is answered or the tools have returned enough). Prompt quality directly determines answer quality. |
| 7 | `notebooks/rag_exploration.ipynb` | Interactive notebook for tuning: chunk size, overlap, embedding model, number of retrieved chunks. Shows what the retriever returns for example queries before wiring it into the agent. RAG quality depends heavily on these parameters — tune them explicitly rather than guessing. |
| 8 | End-to-end agent test | Run the agent on 5 fixed test questions and manually evaluate: did it call the right tools, are citations real PMIDs, is the answer factually consistent with the retrieved abstracts? This is qualitative evaluation — there's no automatic metric for answer quality. |

**Done when:** Agent correctly routes a protein question to UniProt, a literature question to PubMed, and a context question to the vector store — and cites all sources.

---

## Phase 3 — FastAPI serving + Streamlit UI

| # | Task | Why |
|---|------|-----|
| 9 | `src/api/schemas.py` | Pydantic models: QueryRequest (question, max_steps), QueryResponse (answer, citations, steps, latency_ms). `steps` exposes the agent's reasoning — which tools were called, what they returned. Transparency is a feature, not just a debug aid, for a research tool. |
| 10 | `src/api/main.py` | FastAPI app: `POST /query` runs the agent and returns QueryResponse. `/health` checks Ollama connectivity and ChromaDB availability. `/metrics` for Prometheus. Same lifespan pattern as p1/p4 — Ollama client and vector store initialised at startup. |
| 11 | Streamlit chat UI | Chat interface showing the full agent trace: tool calls in an expandable sidebar, final answer in the main panel, citation links to PubMed/UniProt. The trace is what differentiates this from a black-box chatbot — researchers can see *why* the agent said what it said. |
| 12 | `docker-compose.yml` | API + Streamlit + Ollama + ChromaDB. Ollama needs a volume mount for model weights (~4 GB for Llama 3.1 8B Q4). One `docker compose up` for the full local stack. |

---

## Phase 4 — Helm + K8s + CI/CD

| # | Task | Why |
|---|------|-----|
| 13 | `helm/research-agent/` chart | Three deployments: api, streamlit, ollama. Ollama gets a PVC for model weights — model download only happens once. ConfigMap for model name and system prompt (swappable without image rebuild). |
| 14 | GitHub Actions CI | pytest → docker build × 2 (api + streamlit; ollama uses upstream image) → push GHCR → update values.yaml. Ollama is not rebuilt — it's a dependency, not our code. |
| 15 | ArgoCD Application CR | Same GitOps pattern as p1/p4. Adds a third application to the cluster without any new infrastructure. |

---

## Phase 5 — Docs

| # | Task | Why |
|---|------|-----|
| 16 | `docs/q-agent-design.md` | Design document: why agent architecture over a fine-tuned model for this use case, LangGraph vs. LangChain plain, tool design decisions, RAG corpus curation choices, evaluation methodology (and its limits — qualitative eval is honest about what you can't measure automatically). |
| 17 | FAIR data note (inline in agent design doc) | The agent's citation quality depends directly on the underlying data sources having stable identifiers, machine-readable structure, and open access. This is not a theoretical point — it is observed in practice. PubMed works well because it is FAIR. A private, unstructured document store would make grounding much harder. |

---

## Acceptance criteria (project complete)

- [ ] All three tools return correct structured output in isolation (unit tests pass)
- [ ] Agent correctly chains ≥ 2 tools for a multi-step question
- [ ] All citations in agent responses are real, resolvable identifiers (PMIDs / UniProt accessions)
- [ ] FastAPI `/query` returns answer + citations + steps in < 30 s (CPU inference)
- [ ] Streamlit UI shows agent trace alongside answer
- [ ] Deployed to K8s homelab via ArgoCD
- [ ] `docs/q-agent-design.md` written
