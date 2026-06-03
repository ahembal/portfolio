# Design Decisions
*p11 — AI Developer Browser*

---

## Research companion proxies to p6, not a local agent

**Decision:** `/research/stream` is a thin SSE proxy to p6's `/query/stream`. No PubMed,
UniProt, or ChromaDB tools are implemented here.

**Why:**
p6 already has production-tested, deployed implementations of these tools with
error handling, rate limiting, citation extraction, and hallucination checking.
Copying them would create two diverging codebases with no benefit — bugs fixed
in p6 would not apply here and vice versa.

The browser's value-add over p6 is the **interface**: a real browser window with
page context. The research intelligence stays in p6.

This also keeps the backend image small — no sentence-transformers model, no
ChromaDB client, no NCBI dependencies.

---

## Shared Ollama instance with p6

**Decision:** `OLLAMA_BASE_URL` points at p6's Ollama deployment via cross-namespace DNS.

**Why:**
llama3.1:8b requires ~16–18 GB RAM. `quick-thrush` has 64 GB, but running two
Ollama instances would consume ~36 GB just for model weights — plus inference
memory spikes. p6 already manages the model lifecycle (pull, cache in PVC,
health check).

Cross-namespace DNS (`ollama.research-agent.svc.cluster.local:11434`) makes
the shared instance accessible without any infrastructure change. No additional
PVC, no model re-download, no extra scheduling pressure.

The tradeoff is a hard dependency on p6 being deployed and healthy. This is
acceptable at this stage — documented in PROGRESS.md cluster constraints.

---

## LangGraph for the docs agent

**Decision:** Same ReAct graph pattern as p6 (reason → act loop, same state type).

**Why:**
Consistency across the portfolio — a reviewer familiar with p6's agent can
read this one immediately. The pattern handles multi-step cases: if the
companion needs to fetch a linked page for more context, the agent naturally
calls `fetch_page_text` a second time without bespoke orchestration.

A simpler approach (single LLM call with page content in the prompt) would work
for shallow questions but fails when the page links to a referenced API or the
user asks about something not on the current page.

---

## httpx + BeautifulSoup for page reading, not Playwright

**Decision:** `fetch_page_text` uses httpx + BeautifulSoup rather than a headless browser.

**Why:**
Playwright requires a browser binary (~150 MB) in the Docker image, a separate
process per page fetch, and significantly more memory. For documentation sites —
the primary use case — httpx with redirect following is sufficient: docs pages
are server-rendered HTML, not SPAs that require JavaScript execution.

The tradeoff: JavaScript-heavy sites (e.g. some dashboards, SPAs without SSR)
will return thin or empty content. This is acceptable for the current companion
scope (docs, GitHub, which both serve full HTML). Playwright can be added
as a fallback tool later if needed.

---

## Electron shell, not a Chrome extension

**Decision:** Full Electron browser shell, not a Chrome Extension injected into Chrome.

**Why:**
A Chrome extension cannot replace the browser's UI — it can only inject a
sidebar into existing Chrome tabs. This limits the companion panel layout, tab
management, and any custom address bar behaviour.

More importantly: a Chrome extension requires Chrome to be installed and running.
An Electron app is self-contained — it ships its own Chromium, runs without any
external browser, and can be packaged as an AppImage / dmg / installer.

The tradeoff is distribution size (~150 MB for Chromium) and update overhead.
Acceptable for a developer tool aimed at installation, not a one-click web app.

---

## NodePort 30801 for the backend service

**Decision:** Backend exposed as NodePort 30801, following the portfolio's NodePort convention.

**Why:**
p6 Streamlit is on 30651, p1 is on 30080. NodePorts in the 30xxx range are
consistent and memorable. The backend is not user-facing from a browser — the
Electron app calls it directly on localhost (dev) or via cluster DNS (prod).
NodePort is only needed during development and for the health check from outside
the cluster.

---

## Page content passed from the browser, not fetched by the backend

**Decision:** The companion panel extracts page text via `webview.executeJavaScript`
in the renderer and sends it to the backend in the chat request. The backend
does not independently fetch the URL.

**Why:**
The webview has already loaded the page, including any JavaScript-rendered
content, authentication state, and cookies. If the backend fetched the URL
independently via httpx, it would miss all of that — it would see the
unauthenticated, pre-JS version of the page.

This design means the companion always sees exactly what the user sees, without
any re-fetch or authentication duplication.

The tradeoff is a 8000 char limit on what is passed — longer pages are
truncated. The `fetch_page_text` tool can fetch additional linked pages if
needed.
