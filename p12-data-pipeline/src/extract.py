"""
p12 — PubMed extractor.

Fetches abstracts from PubMed via the Entrez API for a given date range.
Returns raw records as a list of dicts. Incremental — only fetches records
published after the last successful run.

Usage:
    from src.extract import fetch

    records = fetch(date_from="2026-01-01", date_to="2026-01-31")
    # returns list of dicts: pmid, title, abstract, pubdate, journal, authors
"""

import logging
import time
from typing import Iterator

from Bio import Entrez, Medline

log = logging.getLogger("p12.extract")

ENTREZ_EMAIL = "emre.balsever@scilifelab.se"
ENTREZ_TOOL  = "p12-data-pipeline"
BATCH_SIZE   = 500
REQUEST_DELAY = 0.34  # stay under 3 req/s without API key


def _configure() -> None:
    Entrez.email = ENTREZ_EMAIL
    Entrez.tool  = ENTREZ_TOOL


def _search(query: str, date_from: str, date_to: str) -> list[str]:
    """Return list of PMIDs matching query within date range."""
    _configure()
    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        datetype="pdat",
        mindate=date_from,
        maxdate=date_to,
        usehistory="y",
        retmax=0,
    )
    result = Entrez.read(handle)
    handle.close()
    count = int(result["Count"])
    log.info("pubmed_search_complete", extra={"query": query, "count": count})

    pmids: list[str] = []
    for start in range(0, count, BATCH_SIZE):
        handle = Entrez.esearch(
            db="pubmed",
            term=query,
            datetype="pdat",
            mindate=date_from,
            maxdate=date_to,
            retstart=start,
            retmax=BATCH_SIZE,
        )
        batch = Entrez.read(handle)
        handle.close()
        pmids.extend(batch["IdList"])
        time.sleep(REQUEST_DELAY)

    return pmids


def _fetch_records(pmids: list[str]) -> Iterator[dict]:
    """Fetch full records for a list of PMIDs in batches."""
    for start in range(0, len(pmids), BATCH_SIZE):
        batch = pmids[start : start + BATCH_SIZE]
        handle = Entrez.efetch(
            db="pubmed",
            id=",".join(batch),
            rettype="medline",
            retmode="text",
        )
        records = list(Medline.parse(handle))
        handle.close()
        time.sleep(REQUEST_DELAY)

        for r in records:
            abstract = r.get("AB", "")
            if not abstract:
                continue
            yield {
                "pmid":     r.get("PMID", ""),
                "title":    r.get("TI", ""),
                "abstract": abstract,
                "pubdate":  r.get("DP", ""),
                "journal":  r.get("JT", ""),
                "authors":  r.get("AU", []),
            }


def fetch(
    date_from: str,
    date_to: str,
    query: str = "pubmed rct[pt]",
) -> list[dict]:
    """
    Fetch PubMed abstracts for a date range.

    Args:
        date_from: YYYY-MM-DD start date (inclusive)
        date_to:   YYYY-MM-DD end date (inclusive)
        query:     Entrez search query (default: randomised controlled trials)

    Returns:
        List of record dicts with keys: pmid, title, abstract, pubdate, journal, authors
    """
    pmids = _search(query, date_from, date_to)
    log.info("fetching_records", extra={"count": len(pmids)})
    records = list(_fetch_records(pmids))
    log.info("extraction_complete", extra={"returned": len(records), "fetched": len(pmids)})
    return records
