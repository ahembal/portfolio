"""
UniProt REST API client.
"""

import requests
from rdflib import Graph


BASE = "https://rest.uniprot.org/uniprotkb"


def fetch_json(accession: str) -> dict:
    resp = requests.get(f"{BASE}/{accession}.json", timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_rdf(accession: str) -> Graph:
    """
    Fetch a protein record as RDF. UniProt publishes native Turtle at
    <accession>.ttl — includes GO terms, diseases, taxonomy, citations.
    """
    resp = requests.get(f"{BASE}/{accession}.ttl", timeout=10)
    resp.raise_for_status()
    g = Graph()
    g.parse(data=resp.text, format="turtle")
    return g
