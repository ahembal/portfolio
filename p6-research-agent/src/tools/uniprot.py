"""
p6-research-agent/src/tools/uniprot.py
----------------------------------------
UniProt REST API wrapper.

lookup(query, organism) → protein record with domains and disease associations.

FAIR data note:
UniProt accession numbers (e.g. P04637 for human TP53) are stable, species-specific
persistent identifiers. Unlike gene symbols (which can be ambiguous across species
or database versions), a UniProt accession is unambiguous and permanently resolvable
at https://www.uniprot.org/uniprot/<accession> — this is what makes protein
citations in the agent's answers trustworthy.
"""

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
TIMEOUT      = 10   # seconds


class UniprotInput(BaseModel):
    query: str
    organism: str = Field(default="human")

    @field_validator("query", mode="before")
    @classmethod
    def uppercase_gene(cls, v):
        return (v or "").upper()

    @field_validator("organism", mode="before")
    @classmethod
    def default_organism(cls, v):
        return v or "human"


@tool("uniprot_lookup", args_schema=UniprotInput)
def lookup(query: str, organism: str = "human") -> dict:
    """
    Look up a protein by gene symbol, protein name, or UniProt accession.

    Searches UniProt for the best-matching reviewed (Swiss-Prot) entry.
    Returns the canonical record for the specified organism.

    Args:
        query:    gene symbol (e.g. "TP53"), protein name, or accession (e.g. "P04637")
        organism: common name or taxon (default "human")

    Returns:
        dict with keys: accession, gene, protein_name, organism, length,
                        domains, diseases, function, url
        Returns {"error": "..."} if not found.

    Example:
        >>> lookup("TP53", organism="human")
        {
          "accession": "P04637",
          "gene": "TP53",
          "protein_name": "Cellular tumor antigen p53",
          "organism": "Homo sapiens",
          "length": 393,
          "domains": ["p53 tetramerisation domain", "DNA-binding domain"],
          "diseases": ["Li-Fraumeni syndrome"],
          "function": "Acts as a tumor suppressor...",
          "url": "https://www.uniprot.org/uniprot/P04637"
        }
    """
    try:
        # Build search query — restrict to reviewed (Swiss-Prot) entries
        search_query = f"gene:{query} AND organism_name:{organism} AND reviewed:true"
        params = {
            "query":  search_query,
            "format": "json",
            "size":   1,
            "fields": "accession,gene_names,protein_name,organism_name,length,"
                      "ft_domain,cc_disease,cc_function",
        }
        resp = requests.get(f"{UNIPROT_BASE}/search", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            # Fallback: try accession direct lookup (if query looks like an accession)
            if len(query) == 6 and query[0].isalpha():
                return _fetch_by_accession(query)
            return {"error": f"No UniProt entry found for '{query}' in {organism}"}

        entry = results[0]
        return _parse_entry(entry)

    except requests.RequestException as e:
        return {"error": f"UniProt API error: {e}"}
    except Exception as e:
        return {"error": str(e)}


def _fetch_by_accession(accession: str) -> dict:
    """Direct accession lookup as fallback."""
    try:
        resp = requests.get(
            f"{UNIPROT_BASE}/{accession}",
            params={"format": "json"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return _parse_entry(resp.json())
    except Exception as e:
        return {"error": str(e)}


def _parse_entry(entry: dict) -> dict:
    """Extract relevant fields from a UniProt JSON entry."""
    accession    = entry.get("primaryAccession", "")
    gene         = ""
    protein_name = ""
    organism     = ""
    length       = 0
    domains      = []
    diseases     = []
    function     = ""

    # Gene name
    genes = entry.get("genes", [])
    if genes:
        gene = genes[0].get("geneName", {}).get("value", "")

    # Protein name
    pname = entry.get("proteinDescription", {})
    rec = pname.get("recommendedName", {})
    full = rec.get("fullName", {})
    protein_name = full.get("value", "")

    # Organism
    org = entry.get("organism", {})
    organism = org.get("scientificName", "")

    # Sequence length
    seq = entry.get("sequence", {})
    length = seq.get("length", 0)

    # Domains from feature table
    features = entry.get("features", [])
    domains = [
        f.get("description", "")
        for f in features
        if f.get("type") == "Domain" and f.get("description")
    ]

    # Disease associations
    comments = entry.get("comments", [])
    for c in comments:
        if c.get("commentType") == "DISEASE":
            disease = c.get("disease", {})
            name = disease.get("diseaseId", "")
            if name:
                diseases.append(name)
        if c.get("commentType") == "FUNCTION":
            texts = c.get("texts", [])
            if texts:
                function = texts[0].get("value", "")[:300]  # truncate long text

    return {
        "accession":    accession,
        "gene":         gene,
        "protein_name": protein_name,
        "organism":     organism,
        "length":       length,
        "domains":      domains,
        "diseases":     diseases,
        "function":     function,
        "url":          f"https://www.uniprot.org/uniprot/{accession}",
    }
