"""
Knowledge graph builder for p9.

Strategy: UniProt-inverted citations.
  1. Start from a curated set of seed proteins.
  2. Each UniProt RDF record embeds PubMed citation URIs.
  3. Extract those PMIDs, fetch the papers from PubMed, and add
     a p9:mentions edge: paper → protein.
  4. Merge the full UniProt RDF into the graph (GO terms, taxonomy,
     disease annotations, isoforms — everything UniProt publishes).

This gives a graph that is connected into the broader linked-data
ecosystem without any NLP or symbol-resolution step.

Usage:
    python src/builder.py                    # default seed proteins
    python src/builder.py P04637 P51587      # custom UniProt accessions
"""

import logging
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from src.aligner import align
from src.clients import pubmed, uniprot

log = logging.getLogger("p9.builder")

P9   = Namespace("http://portfolio/p9/")
SCH  = Namespace("https://schema.org/")
EDAM = Namespace("http://edamontology.org/")
UP   = Namespace("http://purl.uniprot.org/core/")
UPROT = Namespace("http://purl.uniprot.org/uniprot/")

# Canonical proteins spanning TP53/BRCA/EGFR/repair pathways
SEED_PROTEINS: list[tuple[str, str]] = [
    ("P04637", "TP53"),
    ("P38398", "BRCA1"),
    ("P00533", "EGFR"),
    ("P51587", "BRCA2"),
    ("P60484", "PTEN"),
    ("Q00987", "MDM2"),
    ("Q13315", "ATM"),
    ("P01116", "KRAS"),
    ("P06400", "RB1"),
    ("P25054", "APC"),
]

PUBMED_BASE = "http://purl.uniprot.org/pubmed/"
DEFAULT_OUTPUT = Path("data/seed/graph.ttl")
MAX_PAPERS_PER_PROTEIN = 200


def extract_pmids(protein_graph: Graph) -> list[str]:
    """Return PMIDs cited by a UniProt RDF record, capped per protein."""
    pmids: list[str] = []
    for _, _, obj in protein_graph:
        s = str(obj)
        if s.startswith(PUBMED_BASE):
            pmid = s[len(PUBMED_BASE):]
            if pmid.isdigit():
                pmids.append(pmid)
    return list(dict.fromkeys(pmids))[:MAX_PAPERS_PER_PROTEIN]


def paper_to_rdf(data: dict) -> Graph:
    """Convert a PubMed esummary record to RDF triples.

    Paper nodes use UniProt's pubmed URIs (purl.uniprot.org/pubmed/PMID)
    as their primary identifier. UniProt's up:citation edges already point
    to these URIs, so paper → protein traversal works without owl:sameAs
    or OWL inference.
    """
    g = Graph()
    g.bind("p9", P9)
    g.bind("schema", SCH)

    pmid = data["uid"]
    uri  = URIRef(f"{PUBMED_BASE}{pmid}")

    g.add((uri, RDF.type,          P9.Paper))
    g.add((uri, P9.pmid,           Literal(pmid, datatype=XSD.string)))
    g.add((uri, SCH.name,          Literal(data.get("title", ""))))
    g.add((uri, SCH.datePublished, Literal(str(data.get("pubdate", ""))[:4])))

    journal = data.get("source", "")
    if journal:
        g.add((uri, SCH.isPartOf, Literal(journal)))

    for author in data.get("authors", []):
        name     = author.get("name", "")
        auth_uri = P9[f"author_{name.replace(' ', '_').replace(',', '')}"]
        g.add((auth_uri, RDF.type,   P9.Author))
        g.add((auth_uri, SCH.name,   Literal(name)))
        g.add((uri,      SCH.author, auth_uri))

    return g


def build(
    accessions: list[str] | None = None,
    output: Path = DEFAULT_OUTPUT,
) -> Graph:
    """
    Build the full knowledge graph and serialise to Turtle.

    For each seed protein:
      1. Fetch native UniProt Turtle → merge into graph.
      2. Extract cited PMIDs from the UniProt RDF.
      3. Fetch each paper from PubMed → convert to RDF → merge.
      4. Add p9:mentions edge: paper_uri → protein_uri.
    """
    if accessions is None:
        accessions = [acc for acc, _ in SEED_PROTEINS]

    full_graph = Graph()
    full_graph.bind("p9",     P9)
    full_graph.bind("schema", SCH)
    full_graph.bind("edam",   EDAM)
    full_graph.bind("up",     UP)

    seen_pmids: set[str] = set()

    for accession in accessions:
        log.info("fetching UniProt", extra={"accession": accession})
        try:
            protein_graph = uniprot.fetch_rdf(accession)
        except Exception as exc:
            log.warning("UniProt fetch failed", extra={"accession": accession, "error": str(exc)})
            continue

        full_graph += protein_graph

        protein_uri = UPROT[accession]
        pmids = extract_pmids(protein_graph)
        log.info("citations found", extra={"accession": accession, "count": len(pmids)})

        new_pmids = [p for p in pmids if p not in seen_pmids]
        for data in pubmed.fetch_batch(new_pmids):
            pmid = data["uid"]
            seen_pmids.add(pmid)
            full_graph += paper_to_rdf(data)

        # Add p9:mentions for every paper in this protein's citation list,
        # including papers already fetched for a previous protein. Without this,
        # shared papers only get a mentions edge to whichever protein claimed them
        # first — breaking set-intersection queries like Q2 and Q10.
        for pmid in pmids:
            paper_uri = URIRef(f"{PUBMED_BASE}{pmid}")
            full_graph.add((paper_uri, P9.mentions, protein_uri))

    log.info(
        "graph built",
        extra={"proteins": len(accessions), "papers": len(seen_pmids), "triples": len(full_graph)},
    )

    errors = validate(full_graph)
    if errors:
        for e in errors:
            log.warning("validation", extra={"issue": e})
    else:
        log.info("validation passed")

    align(full_graph)
    log.info("edam alignment applied", extra={"triples_after": len(full_graph)})

    output.parent.mkdir(parents=True, exist_ok=True)
    full_graph.serialize(str(output), format="turtle")
    log.info("serialised", extra={"path": str(output)})

    return full_graph


def validate(g: Graph) -> list[str]:
    """Return a list of validation errors; empty list means the graph is clean."""
    errors: list[str] = []

    for paper in g.subjects(RDF.type, P9.Paper):
        if not any(True for _ in g.objects(paper, P9.pmid)):
            errors.append(f"Paper {paper} missing p9:pmid")
        if not any(True for _ in g.objects(paper, SCH.name)):
            errors.append(f"Paper {paper} missing schema:name")

    for _, _, obj in g.triples((None, P9.mentions, None)):
        if not any(True for _ in g.objects(obj, RDF.type)):
            errors.append(f"mentions target {obj} has no rdf:type")

    return errors


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    accessions = sys.argv[1:] if len(sys.argv) > 1 else None
    build(accessions=accessions)
