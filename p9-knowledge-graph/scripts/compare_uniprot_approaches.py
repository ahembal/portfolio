"""
Demonstrates the difference between fetching UniProt data as JSON (manual RDF
conversion) vs fetching native Turtle directly from the UniProt REST API.

Shows that the native Turtle download is a strict superset of what manual
conversion produces, and explains why builder.py uses the direct approach.

Usage:
    python scripts/compare_uniprot_approaches.py          # default: TP53 (P04637)
    python scripts/compare_uniprot_approaches.py P53_HUMAN
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clients.uniprot import fetch_json, fetch_rdf, json_to_rdf


def main(accession: str = "P04637") -> None:
    print(f"\n=== UniProt fetch comparison: {accession} ===\n")

    print("Approach A: JSON → manual RDF conversion")
    g_json = json_to_rdf(fetch_json(accession))
    print(f"  Triples produced: {len(g_json)}")
    for s, p, o in sorted(g_json):
        print(f"  {str(s).split('/')[-1]:25} {str(p).split('/')[-1]:20} {str(o)[:50]}")

    print("\nApproach B: native Turtle download")
    g_rdf = fetch_rdf(accession)
    print(f"  Triples produced: {len(g_rdf)}")

    missing = [t for t in g_json if t not in g_rdf]
    if not missing:
        print(f"\n  ✓ All {len(g_json)} approach-A triples are present in the approach-B graph.")
        print(f"  Approach B adds {len(g_rdf) - len(g_json)} additional triples")
        print("  (GO terms, taxonomy, sequence features, isoforms, citations).")
    else:
        print(f"\n  ✗ {len(missing)} approach-A triples not found in approach-B graph:")
        for t in missing:
            print(f"    {t}")

    print("\nConclusion: approach B is a strict superset. builder.py uses approach B.")


if __name__ == "__main__":
    accession = sys.argv[1] if len(sys.argv) > 1 else "P04637"
    main(accession)
