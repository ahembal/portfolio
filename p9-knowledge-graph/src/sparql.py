"""
SPARQL query interface for p9.

Wraps the Fuseki HTTP endpoint. Results are returned as plain Python dicts
so the caller has no dependency on SPARQLWrapper internals.

Usage:
    client = SPARQLClient("http://localhost:3030/p9")

    rows = client.query('''
        SELECT ?paper ?title WHERE {
          ?paper a p9:Paper ; schema:name ?title .
        } LIMIT 10
    ''')

    for row in rows:
        print(row["title"])
"""

from __future__ import annotations

import os
from typing import Any

from SPARQLWrapper import JSON, SPARQLWrapper

DEFAULT_ENDPOINT = os.getenv("P9_SPARQL_ENDPOINT", "http://localhost:3030/p9/sparql")

_PREFIXES = """\
PREFIX p9:     <http://portfolio/p9/>
PREFIX schema: <https://schema.org/>
PREFIX edam:   <http://edamontology.org/>
PREFIX up:     <http://purl.uniprot.org/core/>
PREFIX uprot:  <http://purl.uniprot.org/uniprot/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
"""


class SPARQLClient:
    """Thin client over the Fuseki SPARQL query endpoint."""

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT) -> None:
        self._endpoint = endpoint
        self._sparql = SPARQLWrapper(endpoint)
        self._sparql.setReturnFormat(JSON)

    def query(self, sparql: str, inject_prefixes: bool = True) -> list[dict[str, Any]]:
        """
        Execute a SELECT query and return results as a list of dicts.

        Each dict maps variable name → string value (URI or literal).
        inject_prefixes=True prepends the standard p9 prefix block.
        """
        full_query = (_PREFIXES + "\n" + sparql) if inject_prefixes else sparql
        self._sparql.setQuery(full_query)
        raw = self._sparql.query().convert()

        bindings = raw.get("results", {}).get("bindings", [])
        return [
            {var: binding[var]["value"] for var in binding}
            for binding in bindings
        ]

    def ask(self, sparql: str, inject_prefixes: bool = True) -> bool:
        """Execute an ASK query and return the boolean result."""
        full_query = (_PREFIXES + "\n" + sparql) if inject_prefixes else sparql
        self._sparql.setQuery(full_query)
        raw = self._sparql.query().convert()
        return bool(raw.get("boolean", False))

    @property
    def endpoint(self) -> str:
        return self._endpoint


def load_query(path: str) -> str:
    """Read a .sparql file from the queries/ directory."""
    with open(path) as f:
        return f.read()
