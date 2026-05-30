"""
Knowledge graph builder for Phase 7 — imaging facilities.

Builds a static RDF graph from src/facilities_seed.py and serialises to
data/seed/facilities.ttl. The facilities graph shares the p9: namespace and
the same Fuseki dataset as the protein/paper graph from Phases 1–6, enabling
cross-domain SPARQL joins (query 13).

Entities and relationships follow the Phase 7 spec in
docs/phase7-facilities-spec.md.

Usage:
    python src/facilities_builder.py
"""

import logging
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from src.facilities_seed import FACILITIES, INITIATIVES, INSTITUTIONS, TECHNIQUES

log = logging.getLogger("p9.facilities_builder")

P9   = Namespace("http://portfolio/p9/")
SCH  = Namespace("https://schema.org/")
EDAM = Namespace("http://edamontology.org/")

DEFAULT_OUTPUT = Path("data/seed/facilities.ttl")


def build(output: Path = DEFAULT_OUTPUT) -> Graph:
    """
    Build the facilities knowledge graph and serialise to Turtle.

    Returns the rdflib Graph for testing or further processing.
    """
    g = Graph()
    g.bind("p9",     P9)
    g.bind("schema", SCH)
    g.bind("edam",   EDAM)

    _add_initiatives(g)
    _add_institutions(g)
    tech_uris = _add_techniques(g)
    _add_facilities(g, tech_uris)

    log.info("facilities graph built", extra={"triples": len(g)})

    output.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(output), format="turtle")
    log.info("serialised", extra={"path": str(output)})

    return g


def _add_initiatives(g: Graph) -> None:
    for item in INITIATIVES:
        uri = P9[f"initiative_{item['id']}"]
        g.add((uri, RDF.type,            P9.Initiative))
        g.add((uri, SCH.name,            Literal(item["name"])))
        g.add((uri, P9.initiativeScope,  Literal(item["scope"])))
        g.add((uri, SCH.url,             Literal(item["homepage"])))


def _add_institutions(g: Graph) -> None:
    for item in INSTITUTIONS:
        uri = P9[f"institution_{item['id']}"]
        g.add((uri, RDF.type,              P9.Institution))
        g.add((uri, RDF.type,              SCH.ResearchOrganization))
        g.add((uri, SCH.name,              Literal(item["name"])))
        g.add((uri, SCH.addressCountry,    Literal(item["country"], datatype=XSD.string)))
        g.add((uri, SCH.url,               Literal(item["homepage"])))


def _add_techniques(g: Graph) -> dict[str, URIRef]:
    """Add Technique nodes and return id→URI mapping for facility wiring."""
    tech_uris: dict[str, URIRef] = {}
    for item in TECHNIQUES:
        uri = P9[f"technique_{item['id']}"]
        tech_uris[item["id"]] = uri
        g.add((uri, RDF.type,        P9.Technique))
        g.add((uri, SCH.name,        Literal(item["name"])))
        g.add((uri, EDAM.has_topic,  EDAM[item["edam_topic"]]))
    return tech_uris


def _add_facilities(g: Graph, tech_uris: dict[str, URIRef]) -> None:
    for item in FACILITIES:
        uri = P9[f"facility_{item['id']}"]
        g.add((uri, RDF.type,                   P9.Facility))
        g.add((uri, SCH.name,                   Literal(item["name"])))
        g.add((uri, SCH.addressLocality,        Literal(item["city"])))
        g.add((uri, P9.accessType,              Literal(item["accessType"])))
        g.add((uri, SCH.parentOrganization,     P9[f"institution_{item['institution']}"]))
        for init_id in item["initiatives"]:
            g.add((uri, P9.nodeOf, P9[f"initiative_{init_id}"]))
        for tech_id in item["techniques"]:
            g.add((tech_uris[tech_id], P9.offeredBy, uri))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    build()
