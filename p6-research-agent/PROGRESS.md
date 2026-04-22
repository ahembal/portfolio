# Project 6 — Life Science Research Agent
## Progress Tracker
*Last updated: 2026-04-21*

---

## Steps

### Phase 1 — Tools
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | src/tools/pubmed.py | ⬜ Todo | PubMed search + fetch via Biopython Entrez. `search(query)` returns PMIDs, `fetch(pmid)` returns structured abstract. Built and tested before the agent — tool bugs are trivial to find in isolation and very hard to find inside an agent loop. |
| 2 | src/tools/uniprot.py | ⬜ Todo | UniProt REST API wrapper. `lookup(gene_symbol)` returns protein name, domains, disease associations, accession. UniProt accession numbers are stable identifiers — a citation to P04637 (TP53) is unambiguous and persistent regardless of how the database evolves. |
| 3 | src/tools/vector_store.py | ⬜ Todo | ChromaDB + sentence-transformers local RAG. `index(documents)` embeds and stores chunks; `search(query, k)` returns top-k relevant chunks. Gives the agent grounding in a local corpus (SciLifeLab platform docs + seed abstracts) beyond what live API calls can provide. |
| 4 | tests/test_tools.py | ⬜ Todo | Unit tests for all three tools with mocked HTTP responses. Validates parsing logic, error handling (rate limits, 404s), and output schema. Tools are pure functions so they are straightforward to test — no agent loop needed. |

### Phase 2 — Agent graph
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 5 | src/agent/graph.py | ⬜ Todo | LangGraph graph: Reason → Act → Respond nodes. The graph makes control flow explicit and inspectable — you can visualise it, add nodes, and test individual steps without running the full loop. State carries the full conversation history and all tool outputs so every node has complete context. |
| 6 | src/agent/prompts.py | ⬜ Todo | System prompt: research assistant role, cite sources inline as [PMID:xxxxx] or [UniProt:Pxxxxx], admit uncertainty, stop when the question is answered. Prompt quality is the primary lever on answer quality — a well-structured prompt does more than a bigger model. |
| 7 | notebooks/rag_exploration.ipynb | ⬜ Todo | Interactive tuning of chunk size, overlap, embedding model, and retrieval k. Shows what the vector store actually returns for example queries before wiring it into the agent. RAG quality is highly sensitive to these parameters and they should be chosen empirically, not guessed. |
| 8 | End-to-end agent evaluation | ⬜ Todo | Run agent on 5 fixed test questions, manually check: right tools called, citations are real resolvable identifiers, answer is consistent with retrieved content. Qualitative eval — there is no automatic metric for answer quality and it is more honest to say so than to report a number that doesn't mean what it seems to. |

### Phase 3 — FastAPI + Streamlit
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 9 | src/api/schemas.py | ⬜ Todo | Pydantic models: QueryRequest (question, max_steps), QueryResponse (answer, citations, steps, latency_ms). Exposing `steps` in the response is deliberate — researchers need to see which tools were called and what they returned to trust the answer. |
| 10 | src/api/main.py | ⬜ Todo | FastAPI app. POST /query runs the agent and returns QueryResponse. /health checks Ollama and ChromaDB. /metrics for Prometheus. Ollama client and vector store initialised at startup in lifespan — same fail-fast pattern as p1 and p4. |
| 11 | streamlit/app.py | ⬜ Todo | Chat UI. Final answer in the main panel; agent trace (tool calls + raw returns) in an expandable sidebar. The trace is what separates this from a black-box chatbot — a researcher can verify the sources rather than just trust the output. |
| 12 | docker-compose.yml | ⬜ Todo | Four services: api, streamlit, ollama (with volume mount for model weights ~4 GB), chromadb. Ollama model pulled on first run and cached in the volume. One `docker compose up` for the full local stack. |

### Phase 4 — Helm + K8s + CI/CD
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 13 | helm/research-agent/ chart | ⬜ Todo | Three deployments: api, streamlit, ollama. Ollama gets a PersistentVolumeClaim for model weights — avoids re-downloading 4 GB on every pod restart. ConfigMap holds model name and system prompt so both can be changed without an image rebuild. |
| 14 | GitHub Actions CI | ⬜ Todo | pytest → docker build api + streamlit → push GHCR → update values.yaml. Ollama uses the upstream image — no rebuild needed. Two images because api and streamlit have different dependencies and different change rates. |
| 15 | ArgoCD Application CR | ⬜ Todo | Adds p6 as a third ArgoCD-managed application on the same cluster. No new infrastructure — demonstrates the GitOps pattern composing across multiple independent services. |

### Phase 5 — Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 16 | docs/q-agent-design.md | ⬜ Todo | Design rationale: why agent architecture over a fine-tuned model, why LangGraph over plain ReAct, tool design decisions, RAG corpus curation, evaluation methodology and its honest limits. The design doc is where the engineering judgement is visible — not just what was built but why each choice was made. |
| 17 | FAIR note in design doc | ⬜ Todo | The agent's citation quality depends directly on PubMed and UniProt being FAIR — stable identifiers, machine-readable structure, open access. This is observed in practice, not argued from theory: a private unstructured document store would make grounding much harder and citations unreliable. Worth stating clearly in the doc because it is a concrete argument for FAIR data infrastructure. |

---

## Quick status

```
Phase 1  [░░░░] 0/4  ← start here
Phase 2  [░░░░] 0/4
Phase 3  [░░░░] 0/4
Phase 4  [░░░]  0/3
Phase 5  [░░]   0/2
```
