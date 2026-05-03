"""
p6-research-agent/src/tools/pubmed.py
--------------------------------------
PubMed search and fetch tools via NCBI Entrez API.

Two functions:
  search(query, max_results) → list of {pmid, title}
  fetch(pmid)                → full abstract + metadata

NCBI Entrez requires an email for identification — not a login,
just a contact address in case the script misbehaves.
Rate limit: 3 requests/second without API key.

FAIR data note:
PubMed records have stable PMIDs as persistent identifiers.
A citation to PMID:37891234 is unambiguous and permanently resolvable
at https://pubmed.ncbi.nlm.nih.gov/<pmid>/ — this is what makes
agent citations trustworthy and verifiable.
"""

import time

from Bio import Entrez, Medline

ENTREZ_EMAIL = "emre.balsever@scilifelab.se"
ENTREZ_TOOL  = "p6-research-agent"
REQUEST_DELAY = 0.35   # seconds between requests — stays under 3/s limit


def _configure():
    Entrez.email = ENTREZ_EMAIL
    Entrez.tool  = ENTREZ_TOOL


def search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search PubMed for papers matching a query.

    Returns a list of {pmid, title} dicts. Does not fetch full abstracts —
    call fetch(pmid) for each result you want to read.

    Args:
        query:       PubMed search query (same syntax as the PubMed web UI)
        max_results: maximum number of results to return (default 5)

    Returns:
        list of dicts with keys: pmid (str), title (str)

    Example:
        >>> search("TP53 glioblastoma 2023", max_results=3)
        [
          {"pmid": "37891234", "title": "TP53 mutation landscape in GBM..."},
          {"pmid": "37654321", "title": "Targeting mutant p53 in glioblastoma..."},
        ]
    """
    _configure()
    try:
        handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results)
        record = Entrez.read(handle)
        handle.close()
        time.sleep(REQUEST_DELAY)

        pmids = record.get("IdList", [])
        if not pmids:
            return []

        # Fetch titles in one batch call (efetch with rettype=medline)
        handle = Entrez.efetch(
            db="pubmed", id=",".join(pmids),
            rettype="medline", retmode="text"
        )
        records = list(Medline.parse(handle))
        handle.close()
        time.sleep(REQUEST_DELAY)

        return [
            {"pmid": r.get("PMID", ""), "title": r.get("TI", "")}
            for r in records
            if r.get("PMID")
        ]
    except Exception as e:
        return [{"error": str(e)}]


def fetch(pmid: str) -> dict:
    """
    Fetch the full abstract and metadata for a single PubMed record.

    Args:
        pmid: PubMed ID string (e.g. "37891234")

    Returns:
        dict with keys: pmid, title, abstract, authors, journal, year, url
        Returns {"error": "..."} if the record cannot be fetched.

    Example:
        >>> fetch("37891234")
        {
          "pmid": "37891234",
          "title": "TP53 mutation landscape in GBM...",
          "abstract": "Background: TP53 mutations occur in...",
          "authors": ["Smith J", "Jones A"],
          "journal": "Nature Cancer",
          "year": "2023",
          "url": "https://pubmed.ncbi.nlm.nih.gov/37891234/"
        }
    """
    _configure()
    try:
        handle = Entrez.efetch(
            db="pubmed", id=pmid,
            rettype="medline", retmode="text"
        )
        records = list(Medline.parse(handle))
        handle.close()
        time.sleep(REQUEST_DELAY)

        if not records:
            return {"error": f"No record found for PMID {pmid}"}

        r = records[0]
        return {
            "pmid":     r.get("PMID", pmid),
            "title":    r.get("TI", ""),
            "abstract": r.get("AB", "No abstract available."),
            "authors":  r.get("AU", []),
            "journal":  r.get("TA", r.get("JT", "")),
            "year":     r.get("DP", "")[:4] if r.get("DP") else "",
            "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }
    except Exception as e:
        return {"error": str(e)}
