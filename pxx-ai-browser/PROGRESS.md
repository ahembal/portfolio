# Project 11 — AI Developer Browser
## Progress Tracker
*Last updated: 2026-05-30*

---

## Cluster constraints
> See `runbooks/known-issues.md` for full details.
- **Schedulable nodes:** `quick-thrush` (primary), `clever-fly` (overflow)
- `sought-perch` is cordoned — do not schedule there (ISS-009)
- **Ollama:** shared with p6 (`ollama.research-agent.svc.cluster.local:11434`) — do not deploy a second instance
- **p6 dependency:** backend requires `research-agent-api.research-agent.svc.cluster.local:8000` — deploy p6 first
- **Image pulls:** copy `ghcr-pull-secret` to `ai-browser` namespace before deploying

---

## Steps

### Phase 1 — Electron shell
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | app/main/index.ts | ✅ Done | BrowserWindow with webview tag. contextIsolation enabled, nodeIntegration disabled — renderer has no Node access. Session header override disables CSP for the webview so any URL loads without interference. titleBarStyle hiddenInset for native feel on Mac. |
| 2 | app/preload/index.ts | ✅ Done | contextBridge exposes `window.electronAPI` — the only surface between renderer and Node. Four methods: companionChat, companionResearch, onCompanionEvent, backendHealth. No Node modules exposed, only typed message-passing primitives. |
| 3 | app/main/companions.ts | ✅ Done | IPC handlers that open HTTP connections to the FastAPI backend and stream SSE events to the renderer. Uses Node's built-in `http` module — no extra dependency. Each SSE line parsed and forwarded as an IPC event so the renderer updates incrementally. |

### Phase 2 — React UI
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | App.tsx — tab management | ✅ Done | Tab state held in React: array of `{ id, url, title }`. Active tab drives both the webview URL and the companion panel context. `key={activeTab.id}` on BrowserView forces a remount per tab — avoids webview reuse bugs across navigations. |
| 5 | TabBar.tsx | ✅ Done | Address bar normalises input: adds `https://` if missing, falls back to Google search for non-URLs. Companion toggle (✦) opens/closes the sidebar without unmounting it — chat history is preserved. |
| 6 | BrowserView.tsx | ✅ Done | Wraps Electron's `<webview>` tag. Listens to `did-navigate` and `did-navigate-in-page` to keep tab title and URL in sync. Exposes webview ref to App so CompanionChat can call `executeJavaScript` to extract page text. |
| 7 | CompanionPanel.tsx + CompanionChat.tsx | ✅ Done | Three companion tabs: Docs Navigator, Research, GitHub. Chat UI streams events: tool_call → tool_result → answer. SSE listener registered once per companion switch. Unsubscribe function returned and called on cleanup to prevent duplicate listeners. |
| 8 | CSS (global.css + app.css) | ✅ Done | Dark theme, purple accent. Split webview / companion panel layout via flexbox. Tab bar with horizontal scroll. No UI framework dependency. |

### Phase 3 — FastAPI backend
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 9 | src/api/schemas.py | ✅ Done | ChatRequest: companion, message, page_url, page_content (max 8000 chars). ResearchRequest: question. HealthResponse: status + per-dependency breakdown. Typed and validated at the boundary. |
| 10 | src/api/main.py — /chat/stream | ✅ Done | LangGraph ReAct agent, same pattern as p6. Page content injected into the message as a context block. SSE via asyncio.Queue + daemon thread — identical to p6's streaming implementation. CORS enabled for Electron renderer origin. |
| 11 | src/api/main.py — /research/stream | ✅ Done | Thin SSE proxy to p6 `/query/stream`. No local agent — httpx AsyncClient streams p6's events unchanged. p6 owns all research tool logic (PubMed, UniProt, ChromaDB). Avoids duplicating tools that are already production-tested. |
| 12 | src/api/main.py — /health + /metrics | ✅ Done | /health checks p6 and Ollama reachability with 3s timeout each. /metrics exposes Prometheus counters and histogram. Same pattern as p1, p2, p6. |
| 13 | src/agent/graph.py | ✅ Done | ReAct graph: reason → act → reason loop. Tool: fetch_page_text. System prompt tuned for developer docs context — separate from p6's research prompt. _build_llm() called per node to avoid persistent connection and allow mocking in tests. |
| 14 | src/tools/page_reader.py | ✅ Done | fetch_page_text tool: httpx GET + BeautifulSoup. Strips nav/footer/script tags before extracting text — removes navigation noise. Returns first 6000 chars. Error-safe: all exceptions returned as dict, never raised. |
| 15 | src/tools/research_client.py | ✅ Done | Async generator that proxies p6's SSE stream. Handles HTTP errors and connection failures — emits an error event and terminates cleanly rather than raising into the FastAPI handler. |

### Phase 4 — Infrastructure
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 16 | backend/Dockerfile | ✅ Done | python:3.11-slim, non-root UID 1000. No playwright in image — page_reader uses httpx+BS4 (lighter, no browser binary). Same security posture as p1/p4/p6. |
| 17 | helm/ai-browser/ | ✅ Done | Deployment, Service (NodePort 30801), ArgoCD Application, Namespace. Cross-namespace DNS to p6 and shared Ollama in values.yaml. Prometheus scrape annotations on the pod. |

### Phase 5 — Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 18 | docs/how-it-works.md | ✅ Done | Three-layer explanation: Electron shell, FastAPI backend, p6 integration. Includes data flow for the Research companion path. |
| 19 | docs/implementation.md | ✅ Done | Per-component build notes, problems hit during development, decisions made along the way. |
| 20 | docs/design-decisions.md | ✅ Done | Why proxy to p6, why shared Ollama, why LangGraph, why httpx+BS4 not Playwright. |
| 21 | docs/observability.md | ✅ Done | Log format, metric definitions, health check logic. |
| 22 | docs/deployment-troubleshooting.md | ✅ Done | Known issues and anticipated failure modes for first cluster deploy. |
| 23 | docs/tools.md | ✅ Done | fetch_page_text and research_client reference. |

### Phase 6 — Browser actions (CDP bridge)
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 24 | app/main/cdp-server.ts | ✅ Done | HTTP server on port 8002 (127.0.0.1 only). Receives action requests from the Python backend and executes them on the active webview via Electron's webContents API. Endpoints: /screenshot, /elements, /click, /type, /navigate, /health. |
| 25 | Active webview tracking | ✅ Done | BrowserView fires `dom-ready` → sends webContentsId via IPC → main stores it → CDP server uses `webContents.fromId()` to resolve the right webview. Required because Electron can have multiple webContents — the CDP server must act on the one the user is looking at. |
| 26 | backend/src/tools/browser_actions.py | ✅ Done | Five LangGraph tools that call the CDP bridge via httpx: browser_screenshot, browser_get_elements, browser_click, browser_type, browser_navigate. All error-safe — return {"error": ...} on failure, never raise. |
| 27 | build_action_graph() | ✅ Done | Second LangGraph graph with all five browser action tools plus fetch_page_text. Separate from the reading graph so the action agent has a different tool set and system prompt without affecting the Docs companion. |
| 28 | agent/prompts.py — ACTION_SYSTEM_PROMPT | ✅ Done | Instructs the agent to always call browser_get_elements before clicking, prefer id selectors, verify actions with a follow-up call, and report exactly what changed. Guards against blind clicking on guessed selectors. |
| 29 | /act/stream endpoint + Act companion tab | ✅ Done | New SSE endpoint in FastAPI. New "Act" companion tab in the React sidebar. Goal text from the user → IPC → companions.ts → /act/stream → LangGraph action agent → CDP bridge → webview. Screenshot image data truncated in SSE events (stays in agent context, not streamed to UI). |

---

## Future work

| # | Task | Notes |
|---|------|-------|
| F1 | GitHub Actions CI | Build backend image, push to GHCR, update values.yaml tag. Same workflow structure as p6. |
| F2 | Electron packaging | `electron-builder` AppImage (Linux) and dmg (Mac) targets already configured in package.json. Needs CI job and release artifact upload. |
| F3 | Windows build target | Add `win: { target: nsis }` to electron-builder config in package.json. No code changes needed — Electron supports Windows natively. |
| F9 | Vision-based clicking | browser_get_elements uses CSS selectors — fails on canvas/iframe elements with no DOM. Add browser_screenshot + vision model (llava via Ollama) to identify click coordinates from a screenshot instead. |
| F4 | GitHub companion system prompt | Currently falls back to Docs Navigator prompt. Needs dedicated prompt tuned for repo/issue/PR context. |
| F5 | Browser history tool | Let companions access recent pages in the current session. Electron main tracks navigation events — expose via IPC and as a LangGraph tool. |
| F6 | Tests | backend/tests/ with pytest-asyncio. Mock httpx for page_reader and research_client. Real FastAPI TestClient for /chat/stream and /health. |
| F7 | Streamlit demo | Web-accessible companion panel for portfolio demo (no Electron required). Accepts a URL as input, calls backend directly. |
| F8 | p6 API NodePort for local dev | p6 API service is ClusterIP — unreachable from outside the cluster. Expose as NodePort or use port-forward for local dev without cluster access. |

---

## Quick status

```
Phase 1 — Electron shell    [███] 3/3  ✅ Done
Phase 2 — React UI          [█████] 5/5  ✅ Done
Phase 3 — FastAPI backend   [███████] 7/7  ✅ Done
Phase 4 — Infrastructure    [██] 2/2  ✅ Done
Phase 5 — Docs              [██████] 6/6  ✅ Done
Phase 6 — Browser actions   [██████] 6/6  ✅ Done
```
