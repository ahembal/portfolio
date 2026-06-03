# How AI Browser Works

## The three layers

### 1. Electron shell (`app/`)

A desktop browser built on Electron. The main process creates a `BrowserWindow`
with a `<webview>` tag — this is a sandboxed Chromium instance that loads any URL.
A React sidebar runs alongside it as the companion panel.

The preload script exposes `window.electronAPI` to the renderer via `contextBridge`.
This is the only bridge between the React UI and the Node.js/Electron main process.
No Node APIs leak into the web context.

When the user sends a message to a companion:
1. React calls `window.electronAPI.companionChat(...)` or `companionResearch(...)`
2. The preload forwards this to the main process via `ipcRenderer.send`
3. The main process opens an HTTP connection to the FastAPI backend and streams SSE
4. Each SSE event is forwarded back to React via `ipcMain` → `event.sender.send`
5. React updates the chat UI incrementally

### 2. FastAPI backend (`backend/`)

Two stream endpoints:

**`/chat/stream`** — for Docs Navigator and GitHub companions.
Runs a LangGraph ReAct agent (same pattern as p6). The current page content is
injected into the system prompt. If the agent needs more context it calls
`fetch_page_text` to retrieve additional pages via httpx + BeautifulSoup.

**`/research/stream`** — for the Research companion.
Does not run a local agent. Instead it opens an SSE connection to p6's
`/query/stream` endpoint and relays events unchanged. This keeps all research
logic (PubMed, UniProt, ChromaDB RAG) in one place.

### 3. p6 Research Agent (external dependency)

The Research companion's brain. When a user asks a research question in the browser,
the request travels:

```
User → Electron → backend /research/stream → p6 /query/stream → LLM + tools
                                                                  ↓
User ← Electron ← backend ←────────────── SSE events ──────────────
```

p6 runs in the `research-agent` Kubernetes namespace. The backend reaches it via
cluster DNS: `research-agent-api.research-agent.svc.cluster.local:8000`.

## Why this design

The browser is deliberately thin — it does not try to replicate p6.
The portfolio already has a tested, deployed research agent. This project
adds the **front-end** (browser shell) and a **general-purpose companion**
(docs/GitHub) that p6 was never designed to handle.

## Running locally

```bash
# Backend
cd backend
pip install -e .
P6_RESEARCH_AGENT_URL=http://100.82.75.34:30XXX uvicorn src.api.main:app --port 8001

# Electron app
npm install
npm run dev
```

The Electron app connects to `http://localhost:8001` by default.
Set `BACKEND_URL` env var to point at the cluster backend.
