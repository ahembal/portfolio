"""
p12 — Feature transformation.

Converts validated raw PubMed records into structured features ready for
the feature store. Each record becomes one row per abstract with sentence-level
annotations where available.

Output schema per record:
    pmid         str   — PubMed identifier
    title        str   — article title
    abstract     str   — full abstract text
    sentences    list  — sentence strings (tokenised)
    pubdate      str   — original publication date string
    year         int   — extracted publication year
    journal      str   — journal name
    n_sentences  int   — sentence count
    char_count   int   — abstract character count
"""

import logging
import re

log = logging.getLogger("p12.transform")

_SENT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')


def transform(records: list[dict]) -> list[dict]:
    """
    Transform validated records into feature-store-ready dicts.

    Args:
        records: list of validated record dicts from src/validate.py

    Returns:
        list of transformed feature dicts
    """
    transformed = []
    for record in records:
        try:
            transformed.append(_transform_one(record))
        except Exception as exc:
            log.warning("transform_failed", extra={"pmid": record.get("pmid"), "error": str(exc)})
    log.info("transform_complete", extra={"input": len(records), "output": len(transformed)})
    return transformed


def _transform_one(record: dict) -> dict:
    abstract = record["abstract"].strip()
    sentences = [s.strip() for s in _SENT_RE.split(abstract) if s.strip()]
    year_match = re.search(r"(\d{4})", record.get("pubdate", ""))
    year = int(year_match.group(1)) if year_match else 0

    return {
        "pmid":        record["pmid"],
        "title":       record.get("title", ""),
        "abstract":    abstract,
        "sentences":   sentences,
        "pubdate":     record.get("pubdate", ""),
        "year":        year,
        "journal":     record.get("journal", ""),
        "n_sentences": len(sentences),
        "char_count":  len(abstract),
    }
