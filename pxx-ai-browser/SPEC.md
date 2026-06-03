# AI Browser — Spec
*Last updated: 2026-05-30*

## What it is

A full Electron-based developer browser with built-in AI companions.
Companions can read the current page, answer questions about it, and delegate
deep research to the p6 Research Agent backend.

## Companions

| Companion | What it does | Backend |
|-----------|-------------|---------|
| Docs Navigator | Reads current page, answers questions about docs, APIs, examples | Local LangGraph agent + page_reader tool |
| Research | Deep research: PubMed, UniProt, ChromaDB RAG | Proxies to p6 `/query/stream` |
| GitHub | Understands repos, issues, PRs from current page | Local LangGraph agent |

## Architecture

```
Electron browser shell
  ├── Chromium webview (standard browsing)
  ├── React sidebar (companion panel)
  └── IPC bridge (preload)
        │
        ▼
FastAPI backend (port 8001)
  ├── GET /chat/stream   — docs/github companions (LangGraph + page_reader)
  ├── GET /research/stream — proxies to p6 /query/stream
  └── GET /health
        │
        ▼
p6 Research Agent (research-agent-api:8000)
  ├── PubMed search + fetch
  ├── UniProt lookup
  └── ChromaDB RAG
```

## Integration with p6

- The Research companion is a thin SSE proxy — no duplication of tools
- Shares p6's Ollama instance (llama3.1:8b on quick-thrush) via cross-namespace K8s DNS
- p6's event schema (tool_call, tool_result, answer, citations, done) is relayed unchanged

## Infrastructure

- Backend: Kubernetes Deployment in `ai-browser` namespace
- Same GitOps pattern as p6: CI writes SHA → ArgoCD syncs
- Prometheus metrics on `/metrics`, scraped by existing cluster Prometheus
- NodePort 30801 for external dev access

## What this is NOT

- Not a Chromium fork — the shell uses Electron's bundled Chromium as-is
- Not a Chrome extension — it is a standalone desktop app
- The backend agent does not replace p6 — it calls p6 for research tasks
