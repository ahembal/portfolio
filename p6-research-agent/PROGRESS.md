# Project 6 — Life Science Research Agent
## Progress Tracker
*Last updated: 2026-05-03*

---

## Cluster constraints
> See `runbooks/known-issues.md` for full details.
- **Schedulable nodes:** `quick-thrush` (primary), `clever-fly` (overflow)
- `sought-perch` is cordoned — do not schedule there (ISS-009)
- **Ollama resource requirement:** Llama 3.1 8B needs ~16 GB RAM for inference
  - Set `resources.requests.memory: 18Gi` on Ollama deployment
  - Schedule explicitly on `quick-thrush` (64 GB RAM)
  - Use a PVC (`ceph-rbd` StorageClass) for model weights — avoid re-downloading 4+ GB on restart
  - PVC volumeMount must use `subPath` (ext4 lost+found issue — see ISS-006)
- **Image pulls:** copy `ghcr-pull-secret` to the new namespace before deploying
- **Image tags:** use full SHA in Helm values (not short SHA) — see ISS-007
- **ChromaDB PVC:** also needs `subPath` if using Ceph RBD

---

## Steps

### Phase 1 — Tools
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | src/tools/pubmed.py | ✅ Done | PubMed is the primary indexed source for biomedical literature. Biopython Entrez is the standard NCBI client — it abstracts rate limiting and Medline parsing. Error-safe returns (dict on any failure) mean a failed search never propagates an exception into the agent loop. |
| 2 | src/tools/uniprot.py | ✅ Done | UniProt is the authoritative, curated source for protein annotations. Structured fields (accession, domains, diseases) make citations verifiable — a researcher can resolve [UniProt:Pxxxxx] directly. This is what makes grounding trustworthy rather than approximate. |
| 3 | src/tools/vector_store.py | ✅ Done | ChromaDB runs embedded (no separate server) — simpler to deploy locally and in K8s. all-MiniLM-L6-v2 is small enough for CPU inference but well-suited for scientific text similarity. Stable chunk IDs allow safe re-indexing without inflating the corpus. |
| 4 | tests/test_tools.py | ✅ Done | Mocking HTTP makes tests deterministic and runnable in CI without hitting NCBI/UniProt rate limits or quotas. Real ChromaDB (not mocked) for vector store tests confirms the embedding pipeline actually works end-to-end — mocking it would give false confidence. |

### Phase 2 — Agent graph
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 5 | src/agent/graph.py | ✅ Done | LangGraph graph: Reason → Act → Respond nodes. The graph makes control flow explicit and inspectable — you can visualise it, add nodes, and test individual steps without running the full loop. State carries the full conversation history and all tool outputs so every node has complete context. |
| 6 | src/agent/prompts.py | ✅ Done | System prompt: research assistant role, cite sources inline as [PMID:xxxxx] or [UniProt:Pxxxxx], admit uncertainty, stop when the question is answered. Prompt quality is the primary lever on answer quality — a well-structured prompt does more than a bigger model. |
| 7 | notebooks/rag_exploration.ipynb | ✅ Done | Interactive tuning of chunk size, overlap, embedding model, and retrieval k. Shows what the vector store actually returns for example queries before wiring it into the agent. RAG quality is highly sensitive to these parameters and they should be chosen empirically, not guessed. |
| 8 | End-to-end agent evaluation | ✅ Done | Run agent on 5 fixed test questions, manually check: right tools called, citations are real resolvable identifiers, answer is consistent with retrieved content. Qualitative eval — there is no automatic metric for answer quality and it is more honest to say so than to report a number that doesn't mean what it seems to. |

### Phase 3 — FastAPI + Streamlit
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 9 | src/api/schemas.py | ✅ Done | Pydantic models: QueryRequest (question, max_steps), QueryResponse (answer, citations, steps, latency_ms). Exposing `steps` in the response is deliberate — researchers need to see which tools were called and what they returned to trust the answer. |
| 10 | src/api/main.py | ✅ Done | FastAPI app. POST /query runs the agent and returns QueryResponse. /health checks Ollama and ChromaDB. /metrics for Prometheus. Ollama client and vector store initialised at startup in lifespan — same fail-fast pattern as p1 and p4. |
| 11 | streamlit/app.py | ✅ Done | Chat UI. Final answer in the main panel; agent trace (tool calls + raw returns) in an expandable sidebar. The trace is what separates this from a black-box chatbot — a researcher can verify the sources rather than just trust the output. |
| 12 | docker-compose.yml | ✅ Done | Four services: api, streamlit, ollama (with volume mount for model weights ~4 GB), chromadb. Ollama model pulled on first run and cached in the volume. One `docker compose up` for the full local stack. |

### Phase 4 — Helm + K8s + CI/CD
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 13 | helm/research-agent/ chart | ✅ Done | Three deployments: api, streamlit, ollama. Ollama gets a PersistentVolumeClaim for model weights — avoids re-downloading 4 GB on every pod restart. ConfigMap holds model name and system prompt so both can be changed without an image rebuild. |
| 14 | GitHub Actions CI | ✅ Done | pytest → docker build api + streamlit → push GHCR → update values.yaml. Ollama uses the upstream image — no rebuild needed. Two images because api and streamlit have different dependencies and different change rates. |
| 15 | ArgoCD Application CR | ✅ Done | Adds p6 as a third ArgoCD-managed application on the same cluster. No new infrastructure — demonstrates the GitOps pattern composing across multiple independent services. |

### Phase 5 — Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 16 | docs/q-agent-design.md | ✅ Done | Design rationale: why agent architecture over a fine-tuned model, why LangGraph over plain ReAct, tool design decisions, RAG corpus curation, evaluation methodology and its honest limits. The design doc is where the engineering judgement is visible — not just what was built but why each choice was made. |
| 17 | FAIR note in design doc | ✅ Done | The agent's citation quality depends directly on PubMed and UniProt being FAIR — stable identifiers, machine-readable structure, open access. This is observed in practice, not argued from theory: a private unstructured document store would make grounding much harder and citations unreliable. Worth stating clearly in the doc because it is a concrete argument for FAIR data infrastructure. |

---

## Future work

| # | Task | Notes |
|---|------|-------|
| F1 | Move portfolio Streamlit to repo root | Currently lives in `p6-research-agent/streamlit/` as it was the first project to have a UI. Should be extracted to `portfolio-ui/` at the repo root with its own image, Helm chart, and CI job — independent of p6. |
| F2 | Streaming agent responses | Replace `graph.invoke()` with `graph.astream()` + SSE endpoint so tool calls appear in the UI as they happen, not after completion. |
| F3 | Filter PubMed results to English only | Add `AND English[Language]` to the Entrez query in `pubmed_search()`. Currently non-English papers can be returned — the LLM may silently produce a wrong summary of a non-English abstract. Simple one-line fix but changes behaviour so kept as explicit decision. |
| F4 | Fix system prompt — require pubmed_fetch before citing | Current prompt says "use minimum tool calls" which causes the LLM to answer from titles only. Update to explicitly require `pubmed_fetch` on top results before citing. See `docs/q-agent-design.md` — Prompt engineering section. |
| F5 | Implement citation provenance validation | Cross-reference PMIDs and UniProt accessions in the answer against the tool call history. Flag any citation that was not actually retrieved in the session. See `docs/answer-quality.md`. |
| F6 | Prevent hallucinated citations at the source — prompt fix | ✅ Done (2026-05-27). Rule 3 in `src/agent/prompts.py` now explicitly requires verifying each ID appeared in tool results before citing it. The post-processing strip remains as a safety net. Needs evaluation against the p7 benchmark to confirm citation recall on verified sources is not reduced — benchmark requires Ollama running locally. |

---

## Quick status

```
Phase 1  [████] 4/4  ✅ Done
Phase 2  [████] 4/4  ✅ Done
Phase 3  [████] 4/4  ✅ Done
Phase 4  [███]  3/3  ✅ Done
Phase 5  [██]   2/2  ✅ Done
```
