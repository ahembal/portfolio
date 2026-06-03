"""
Browser action tools — call the Electron CDP bridge (localhost:8002)
to interact with the visible webview.

The agent uses these to actually drive the browser:
  1. browser_screenshot  — see what the page looks like
  2. browser_get_elements — list clickable/typeable elements
  3. browser_click       — click an element by CSS selector
  4. browser_type        — fill an input field
  5. browser_navigate    — go to a URL

All tools are error-safe: exceptions return {"error": ...}, never raise.
The agent receives errors as data and can decide how to recover.
"""

import os

import httpx
from langchain_core.tools import tool

CDP_URL = os.getenv("CDP_BRIDGE_URL", "http://127.0.0.1:8002")
_TIMEOUT = 15


def _post(path: str, body: dict | None = None) -> dict:
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.post(f"{CDP_URL}{path}", json=body or {})
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as exc:
        return {"error": f"CDP bridge {exc.response.status_code}: {exc.response.text[:200]}"}
    except Exception as exc:
        return {"error": str(exc)}


@tool
def browser_screenshot() -> dict:
    """Take a screenshot of the current browser page.
    Returns {"image": "<base64 PNG>", "format": "png"} or {"error": "..."}.
    Use this to see the current state of the page before and after actions.
    """
    return _post("/screenshot")


@tool
def browser_get_elements() -> dict:
    """List all visible interactive elements on the current page.
    Returns {"elements": [...]} where each element has:
      index, tag, type, text, selector (CSS id selector if available), href, name.
    Use this to find the right element to click or type into before acting.
    """
    return _post("/elements")


@tool
def browser_click(selector: str) -> dict:
    """Click an element on the page by CSS selector.
    Use the selector from browser_get_elements (e.g. '#submit-btn').
    If no id selector is available, use tag + attribute (e.g. 'button[name="search"]').
    Returns {"ok": true, "tag": "...", "text": "..."} or {"error": "..."}.
    """
    return _post("/click", {"selector": selector})


@tool
def browser_type(selector: str, text: str) -> dict:
    """Type text into an input field identified by CSS selector.
    Clears the existing value and sets the new one.
    Dispatches input and change events so React/Vue forms detect the change.
    Returns {"ok": true} or {"error": "..."}.
    """
    return _post("/type", {"selector": selector, "text": text})


@tool
def browser_navigate(url: str) -> dict:
    """Navigate the browser to a URL.
    Use when the task requires going to a specific page.
    Returns {"ok": true, "url": "..."} or {"error": "..."}.
    """
    return _post("/navigate", {"url": url})
