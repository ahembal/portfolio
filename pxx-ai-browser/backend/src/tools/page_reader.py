"""
Tool: fetch_page_text
Fetches the visible text of a URL using httpx + BeautifulSoup.
Used when the companion needs more context beyond what was passed from the browser.
"""

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool


@tool
def fetch_page_text(url: str) -> dict:
    """Fetch the visible text content of a web page by URL.
    Use this when you need more detail from a page beyond what the user shared.
    Returns a dict with 'url' and 'text' (first 6000 chars) or 'error'.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (AI Browser companion; research use)"}
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        return {"error": f"HTTP error fetching {url}: {exc}"}
    except Exception as exc:
        return {"error": str(exc)}

    soup = BeautifulSoup(r.text, "html.parser")

    # Remove nav/footer noise
    for tag in soup(["nav", "footer", "script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    return {"url": url, "text": text[:6000]}
