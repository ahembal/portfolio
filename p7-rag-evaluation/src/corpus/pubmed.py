"""
Corpus population — fetch PubMed abstracts and index into ChromaDB.

Fetches abstracts for a predefined set of life science topics and upserts
them into the vector store. Designed to run at startup and on a schedule.
Already-indexed documents are skipped (upsert by stable ID).
"""

import time
from Bio import Entrez, Medline

ENTREZ_EMAIL   = "emre.balsever@scilifelab.se"
ENTREZ_TOOL    = "p7-rag-evaluation"
REQUEST_DELAY  = 0.35  # stay under NCBI 3 req/s limit

# Topics to seed the corpus with. Each entry produces up to MAX_PER_TOPIC abstracts.
SEED_TOPICS = [
    "TP53 tumour suppressor",
    "BRCA1 BRCA2 DNA repair",
    "EGFR targeted therapy cancer",
    "mTOR signalling pathway",
    "immunotherapy checkpoint inhibitor",
    "CRISPR Cas9 gene editing",
    "glioblastoma treatment",
    "colorectal cancer biomarkers",
    "CAR-T cell therapy",
    "single cell RNA sequencing",
]

MAX_PER_TOPIC = 10


def _configure():
    Entrez.email = ENTREZ_EMAIL
    Entrez.tool  = ENTREZ_TOOL


def fetch_topic(topic: str, max_results: int = MAX_PER_TOPIC) -> list[dict]:
    """
    Fetch PubMed abstracts for a single topic query.

    Returns a list of dicts with keys: pmid, title, abstract, source.
    Documents with no abstract are skipped.
    """
    _configure()
    try:
        query = f"({topic}) AND English[Language] AND hasabstract"
        handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results, sort="relevance")
        record = Entrez.read(handle)
        handle.close()
        time.sleep(REQUEST_DELAY)

        pmids = record.get("IdList", [])
        if not pmids:
            return []

        handle = Entrez.efetch(
            db="pubmed", id=",".join(pmids),
            rettype="medline", retmode="text"
        )
        records = list(Medline.parse(handle))
        handle.close()
        time.sleep(REQUEST_DELAY)

        docs = []
        for r in records:
            abstract = r.get("AB", "").strip()
            pmid     = r.get("PMID", "")
            title    = r.get("TI", "")
            if not abstract or not pmid:
                continue
            docs.append({
                "pmid":     pmid,
                "title":    title,
                "abstract": abstract,
                "text":     f"{title}\n\n{abstract}",
                "source":   f"pubmed:{pmid}",
            })
        return docs

    except Exception as e:
        return [{"error": str(e)}]


def populate(topics: list[str] = None, max_per_topic: int = MAX_PER_TOPIC) -> dict:
    """
    Fetch abstracts for all topics and return as a list of documents ready for indexing.

    Args:
        topics:        list of PubMed query strings (defaults to SEED_TOPICS)
        max_per_topic: max abstracts per topic

    Returns:
        dict with keys:
          documents  — list of {text, source, pmid, title} dicts
          stats      — {topics_fetched, documents_fetched, errors}
    """
    if topics is None:
        topics = SEED_TOPICS

    all_docs = []
    errors   = 0
    seen_pmids: set[str] = set()

    for topic in topics:
        results = fetch_topic(topic, max_per_topic)
        for doc in results:
            if "error" in doc:
                errors += 1
                continue
            pmid = doc["pmid"]
            if pmid in seen_pmids:
                continue
            seen_pmids.add(pmid)
            all_docs.append(doc)

    return {
        "documents": all_docs,
        "stats": {
            "topics_fetched":    len(topics),
            "documents_fetched": len(all_docs),
            "errors":            errors,
        },
    }
