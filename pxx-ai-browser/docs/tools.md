# Tools
*p11 — AI Developer Browser*

The docs/GitHub companions use two tools. The research companion bypasses these
entirely and delegates to p6 — see `design-decisions.md`.

---

## fetch_page_text

**File:** `backend/src/tools/page_reader.py`
**Used by:** Docs Navigator, GitHub companion

Fetches the visible text content of a URL via httpx + BeautifulSoup.

The companion calls this when it needs more context than what was passed from
the browser (e.g. the user asks about something on a linked page).

**Input:**

| Field | Type | Description |
|-------|------|-------------|
| `url` | str | The full URL to fetch |

**Output (success):**

```json
{
  "url": "https://docs.python.org/3/library/asyncio.html",
  "text": "asyncio — Asynchronous I/O\n\nasyncio is a library..."
}
```

`text` is the first 6000 characters of visible page text after removing
`<nav>`, `<footer>`, `<script>`, `<style>`, and `<noscript>` tags.

**Output (error):**

```json
{
  "error": "HTTP error fetching https://...: 404 Not Found"
}
```

Always returns a dict — never raises. The agent receives the error as data
and can report it to the user or try a different URL.

**Limitations:**
- JavaScript-rendered pages (SPAs without SSR) return empty or minimal content —
  `innerText` is not available without a real browser runtime
- Requires the page to be publicly accessible — authenticated pages will return
  the login page, not the content

---

## browser_screenshot

**File:** `backend/src/tools/browser_actions.py`
**Used by:** Act companion

Captures the current webview as a base64 PNG via the CDP bridge.
Returns `{"image": "<base64>", "format": "png"}` or `{"error": "..."}`.

The agent uses this to see the current page state before and after actions.
Image data is kept in the agent's context window but truncated in SSE events
sent to the React sidebar (to avoid flooding the UI with base64 strings).

---

## browser_get_elements

**File:** `backend/src/tools/browser_actions.py`
**Used by:** Act companion

Lists all visible interactive elements on the current page via `executeJavaScript`.
Filters to elements with non-zero bounding box within the viewport. Returns up to 60 elements.

Each element: `{ index, tag, type, text, selector, href, name }`.

The agent calls this before every click to find the right CSS selector — it never
guesses selectors without first seeing what is on the page.

---

## browser_click

**File:** `backend/src/tools/browser_actions.py`
**Used by:** Act companion

Clicks an element by CSS selector via `executeJavaScript`.
Scrolls the element into view and calls `.focus()` then `.click()` on it.
Returns `{"ok": true, "tag": "...", "text": "..."}` or `{"error": "element not found: ..."}`.

---

## browser_type

**File:** `backend/src/tools/browser_actions.py`
**Used by:** Act companion

Fills an input field identified by CSS selector.
Sets `.value`, then dispatches `input` and `change` events so React/Vue
forms detect the programmatic change.
Returns `{"ok": true}` or `{"error": "..."}`.

---

## browser_navigate

**File:** `backend/src/tools/browser_actions.py`
**Used by:** Act companion

Navigates the webview to a URL via `webContents.loadURL()`.
Returns `{"ok": true, "url": "..."}` or `{"error": "..."}`.

---

## research_client (p6 proxy)

**File:** `backend/src/tools/research_client.py`
**Used by:** Research companion (`/research/stream` endpoint directly, not as a LangGraph tool)

Async generator that proxies p6's SSE stream to the browser.

```
Browser → /research/stream → stream_research() → p6 /query/stream
                                                    ├── pubmed_search
                                                    ├── pubmed_fetch
                                                    ├── uniprot_lookup
                                                    └── rag_search (ChromaDB)
```

**Events relayed (p6 schema, passed through unchanged):**

| Type | Payload | Meaning |
|------|---------|---------|
| `tool_call` | `{ tool, args }` | p6 agent is calling a tool |
| `tool_result` | `{ tool, content }` | Tool returned a result |
| `answer` | `{ content }` | Final answer text |
| `citations` | `{ citations: [...] }` | Extracted PubMed / UniProt citations |
| `done` | — | Stream complete |
| `error` | `{ message }` | p6 error or connection failure |

The `done` event is always emitted — even on connection error — so the frontend
never hangs waiting for a termination signal.

See p6's `docs/tools.md` for full documentation of the research tools
(pubmed_search, pubmed_fetch, uniprot_lookup, rag_search).
