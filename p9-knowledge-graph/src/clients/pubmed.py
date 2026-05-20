"""
PubMed E-utilities API client.
"""

import time

import requests


BASE  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DELAY = 0.1  # NCBI allows 10 requests/s without an API key


def search(query: str, max_results: int = 100) -> list[str]:
    """Return a list of PMIDs matching the query."""
    resp = requests.get(
        f"{BASE}/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["esearchresult"]["idlist"]


def fetch(pmid: str) -> dict:
    """Return the summary record for a single PMID."""
    resp = requests.get(
        f"{BASE}/esummary.fcgi",
        params={"db": "pubmed", "id": pmid, "retmode": "json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["result"][pmid]


def fetch_batch(pmids: list[str]) -> list[dict]:
    """Fetch multiple records, respecting the NCBI rate limit."""
    results = []
    for pmid in pmids:
        try:
            results.append(fetch(pmid))
            time.sleep(DELAY)
        except Exception:
            pass
    return results
