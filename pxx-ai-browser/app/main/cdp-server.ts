/**
 * CDP bridge — tiny HTTP server on port 8002.
 * The Python backend calls this to execute browser actions on the active webview.
 *
 * Endpoints:
 *   GET  /health                    — liveness check
 *   POST /screenshot                — capture current webview as base64 PNG
 *   POST /elements                  — list visible interactive elements
 *   POST /click   { selector }      — click an element by CSS selector
 *   POST /type    { selector, text }— fill an input field
 *   POST /navigate { url }          — navigate the webview to a URL
 *   POST /eval    { script }        — run arbitrary JS (internal use only)
 */

import * as http from "http";
import { webContents } from "electron";

let _activeWebContentsId: number | null = null;

export function setActiveWebContentsId(id: number): void {
  _activeWebContentsId = id;
}

function getActive() {
  if (_activeWebContentsId === null) return null;
  return webContents.fromId(_activeWebContentsId) ?? null;
}

// JS injected into the webview to collect visible interactive elements
const COLLECT_ELEMENTS_SCRIPT = `
(function() {
  function getSelector(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
    const text = (el.innerText || '').trim().slice(0, 30);
    if (text) return el.tagName.toLowerCase() + ':contains-text-approximation';
    return el.tagName.toLowerCase();
  }
  const candidates = Array.from(
    document.querySelectorAll('a, button, input, select, textarea, [role="button"], [role="link"], [onclick]')
  ).filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.top >= 0 && r.top < window.innerHeight;
  }).slice(0, 60);

  return JSON.stringify(candidates.map((el, i) => ({
    index: i,
    tag: el.tagName.toLowerCase(),
    type: el.getAttribute('type') || null,
    text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim().slice(0, 120),
    selector: el.id ? '#' + CSS.escape(el.id) : null,
    href: el.href || null,
    name: el.getAttribute('name') || null,
  })));
})()
`;

const CLICK_SCRIPT = (selector: string) => `
(function() {
  const el = document.querySelector(${JSON.stringify(selector)});
  if (!el) return JSON.stringify({ error: 'element not found: ' + ${JSON.stringify(selector)} });
  el.scrollIntoView({ block: 'center' });
  el.focus();
  el.click();
  return JSON.stringify({ ok: true, tag: el.tagName.toLowerCase(), text: (el.innerText || '').trim().slice(0, 80) });
})()
`;

const TYPE_SCRIPT = (selector: string, text: string) => `
(function() {
  const el = document.querySelector(${JSON.stringify(selector)});
  if (!el) return JSON.stringify({ error: 'element not found: ' + ${JSON.stringify(selector)} });
  el.focus();
  el.value = ${JSON.stringify(text)};
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return JSON.stringify({ ok: true });
})()
`;

async function handleRequest(
  req: http.IncomingMessage,
  res: http.ServerResponse
): Promise<void> {
  const url = req.url ?? "/";
  const method = req.method ?? "GET";

  res.setHeader("Content-Type", "application/json");

  // Health
  if (method === "GET" && url === "/health") {
    res.writeHead(200);
    res.end(JSON.stringify({ status: "ok", hasActiveWebview: _activeWebContentsId !== null }));
    return;
  }

  // Parse body for POST requests
  let body: Record<string, string> = {};
  if (method === "POST") {
    body = await new Promise((resolve) => {
      let raw = "";
      req.on("data", (chunk) => (raw += chunk.toString()));
      req.on("end", () => {
        try { resolve(JSON.parse(raw)); }
        catch { resolve({}); }
      });
    });
  }

  const wc = getActive();
  if (!wc) {
    res.writeHead(503);
    res.end(JSON.stringify({ error: "no active webview" }));
    return;
  }

  try {
    if (method === "POST" && url === "/screenshot") {
      const image = await wc.capturePage();
      const png = image.toPNG();
      res.writeHead(200);
      res.end(JSON.stringify({ image: png.toString("base64"), format: "png" }));

    } else if (method === "POST" && url === "/elements") {
      const result = await wc.executeJavaScript(COLLECT_ELEMENTS_SCRIPT);
      res.writeHead(200);
      res.end(JSON.stringify({ elements: JSON.parse(result as string) }));

    } else if (method === "POST" && url === "/click") {
      if (!body.selector) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: "selector required" }));
        return;
      }
      const result = await wc.executeJavaScript(CLICK_SCRIPT(body.selector));
      res.writeHead(200);
      res.end(result as string);

    } else if (method === "POST" && url === "/type") {
      if (!body.selector || body.text === undefined) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: "selector and text required" }));
        return;
      }
      const result = await wc.executeJavaScript(TYPE_SCRIPT(body.selector, body.text));
      res.writeHead(200);
      res.end(result as string);

    } else if (method === "POST" && url === "/navigate") {
      if (!body.url) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: "url required" }));
        return;
      }
      await wc.loadURL(body.url);
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, url: body.url }));

    } else {
      res.writeHead(404);
      res.end(JSON.stringify({ error: "not found" }));
    }
  } catch (err) {
    res.writeHead(500);
    res.end(JSON.stringify({ error: String(err) }));
  }
}

export function startCDPServer(port = 8002): void {
  const server = http.createServer((req, res) => {
    handleRequest(req, res).catch((err) => {
      res.writeHead(500);
      res.end(JSON.stringify({ error: String(err) }));
    });
  });
  server.listen(port, "127.0.0.1", () => {
    console.log(`CDP bridge listening on 127.0.0.1:${port}`);
  });
}
