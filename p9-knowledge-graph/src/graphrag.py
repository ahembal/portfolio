"""
GraphRAG — hybrid retrieval combining SPARQL graph traversal with p7 vector search.

Given a question:
  1. Extract protein entities from the question (gene name → UniProt accession)
  2. SPARQL traversal: pull graph facts (co-mentions, diseases, paper titles)
  3. Vector retrieval: query p7 ChromaDB using entity names as the search string
  4. LLM synthesis: ground the answer in both graph facts and retrieved passages

Handles hybrid questions that are partially structured (entity relationships)
and partially open-ended (explanation, synthesis) — questions where SPARQL alone
returns facts without meaning, and RAG alone returns meaning without precision.

Usage:
    from src.graphrag import GraphRAG
    grag = GraphRAG()
    result = grag.query("Which proteins are mentioned in BRCA1 papers, and what do we know about their function?")
    print(result["answer"])
    print(result["graph_context"])
    print(result["retrieved_passages"])
"""

from __future__ import annotations

import os
import sys
from typing import Any

from src.sparql import SPARQLClient

# Gene name → UniProt accession for the 10 seed proteins
PROTEIN_MAP: dict[str, str] = {
    "TP53":  "P04637",
    "EGFR":  "P00533",
    "ATM":   "Q13315",
    "BRCA1": "P38398",
    "RB1":   "P06400",
    "BRCA2": "P51587",
    "PTEN":  "P60484",
    "MDM2":  "Q00987",
    "APC":   "P25054",
    "KRAS":  "P01116",
}

# Reverse map: accession → gene name (for display)
ACCESSION_MAP = {v: k for k, v in PROTEIN_MAP.items()}

DEFAULT_P7_ROOT = os.getenv(
    "P7_ROOT",
    os.path.join(os.path.dirname(__file__), "..", "..", "p7-rag-evaluation"),
)


def _load_llm():
    """Load the LLM independently of p7. Returns llm or None."""
    try:
        from langchain_ollama import ChatOllama  # type: ignore
        return ChatOllama(model=os.getenv("GRAPHRAG_LLM", "llama3.1:8b"))
    except Exception as e:
        print(f"LLM not available ({e}) — answers will be raw graph context.")
        return None


def _load_p7(p7_root: str):
    """Import p7 retrieval pipeline. Returns retrieve_fn or None."""
    try:
        # Clear any cached src.* from p9 before importing p7
        for k in list(sys.modules):
            if k == "src" or k.startswith("src."):
                del sys.modules[k]
        sys.path.insert(0, os.path.abspath(p7_root))
        from src.retrieval.pipeline import retrieve  # type: ignore
        return retrieve
    except Exception as e:
        print(f"p7 not available ({e}) — GraphRAG will run without vector retrieval.")
        return None
    finally:
        # Clear p7's src so p9 imports work normally after this call
        for k in list(sys.modules):
            if k == "src" or k.startswith("src."):
                del sys.modules[k]


def _extract_proteins(question: str) -> list[str]:
    """Return UniProt accessions for protein gene names found in the question."""
    q = question.upper()
    return [acc for gene, acc in PROTEIN_MAP.items() if gene in q]


def _sparql_context(client: SPARQLClient, accessions: list[str]) -> dict[str, Any]:
    """
    Pull three types of graph facts for the given proteins:
      - recent papers mentioning them (up to 10 per protein)
      - proteins co-mentioned in the same papers
      - diseases associated with those proteins
    """
    if not accessions:
        return {"papers": [], "co_proteins": [], "diseases": []}

    values_block = " ".join(f"uprot:{a}" for a in accessions)

    papers = client.query(f"""
        SELECT DISTINCT ?title ?year WHERE {{
          ?paper a p9:Paper ;
                 schema:name ?title ;
                 schema:datePublished ?year ;
                 p9:mentions ?protein .
          VALUES ?protein {{ {values_block} }}
        }}
        ORDER BY DESC(?year)
        LIMIT 10
    """)

    co_proteins = client.query(f"""
        SELECT DISTINCT ?other (COUNT(DISTINCT ?paper) AS ?shared) WHERE {{
          ?paper p9:mentions ?protein ;
                 p9:mentions ?other .
          VALUES ?protein {{ {values_block} }}
          FILTER(?other NOT IN ( {values_block} ))
        }}
        GROUP BY ?other
        HAVING (COUNT(DISTINCT ?paper) >= 2)
        ORDER BY DESC(?shared)
        LIMIT 10
    """)

    diseases = client.query(f"""
        SELECT DISTINCT ?disease WHERE {{
          ?protein up:annotation ?ann .
          ?ann a up:Disease_Annotation ;
               rdfs:comment ?disease .
          VALUES ?protein {{ {values_block} }}
        }}
        ORDER BY ?disease
        LIMIT 20
    """)

    # Include co-mentioned proteins in the function annotation query
    co_accessions = [
        r["other"].split("/")[-1]
        for r in co_proteins
        if r["other"].split("/")[-1] in ACCESSION_MAP
    ]
    all_accessions = list(set(accessions + co_accessions))
    all_values_block = " ".join(f"uprot:{a}" for a in all_accessions)

    functions = client.query(f"""
        SELECT ?protein ?function WHERE {{
          ?protein up:annotation ?ann .
          ?ann a up:Function_Annotation ;
               rdfs:comment ?function .
          VALUES ?protein {{ {all_values_block} }}
        }}
    """)

    return {
        "papers":      [(r["title"], r.get("year", "")) for r in papers],
        "co_proteins": [
            (ACCESSION_MAP.get(r["other"].split("/")[-1], r["other"].split("/")[-1]),
             r["shared"])
            for r in co_proteins
        ],
        "diseases":    [r["disease"] for r in diseases],
        "functions":   [
            (ACCESSION_MAP.get(r["protein"].split("/")[-1], r["protein"].split("/")[-1]),
             r["function"])
            for r in functions
        ],
    }


def _format_graph_context(ctx: dict[str, Any], accessions: list[str]) -> str:
    genes = [ACCESSION_MAP.get(a, a) for a in accessions]
    lines = [f"Graph facts for: {', '.join(genes)}"]

    if ctx["papers"]:
        lines.append("\nRecent papers:")
        for title, year in ctx["papers"]:
            lines.append(f"  [{year}] {title}")

    if ctx["co_proteins"]:
        lines.append("\nFrequently co-mentioned proteins:")
        for gene, count in ctx["co_proteins"]:
            lines.append(f"  {gene} (shared in {count} papers)")

    if ctx["functions"]:
        lines.append("\nProtein functions:")
        for gene, func in ctx["functions"]:
            lines.append(f"  {gene}: {func[:300]}")

    if ctx["diseases"]:
        lines.append("\nAssociated diseases:")
        for d in ctx["diseases"]:
            lines.append(f"  {d}")

    return "\n".join(lines)


def _synthesise(question: str, graph_context: str, passages: list[str], llm) -> str:
    from langchain_core.messages import HumanMessage

    passages_text = "\n---\n".join(passages) if passages else "(none)"
    prompt = f"""\
You are a biomedical research assistant. Answer the question using ONLY the
information provided below. Do not add knowledge not present in the sources.
Use ALL relevant facts from the graph — especially the protein functions listed.

Important framing rules:
- The graph records which proteins co-occur in the same papers. Say
  "co-mentioned with X in the papers represented in the graph" — not
  "associated with X", which implies a direct biological relationship
  the graph does not assert.
- When listing proteins with their functions, end with a single broad
  sentence covering the shared biological themes (e.g. DNA repair,
  checkpoint signalling, cell-cycle control, cancer pathways) rather
  than restating one specific mechanism.

Question: {question}

Graph facts (structured, exact):
{graph_context}

Retrieved passages (unstructured text):
{passages_text}

Answer each part of the question explicitly. List each protein with its function:"""

    return llm.invoke([HumanMessage(content=prompt)]).content.strip()


class GraphRAG:
    """
    Hybrid retrieval: SPARQL graph traversal + p7 vector search + LLM synthesis.

    If p7 is not available (missing deps or ChromaDB not populated), falls back
    to graph-only context passed directly to the LLM.
    """

    def __init__(
        self,
        sparql_endpoint: str | None = None,
        p7_root: str = DEFAULT_P7_ROOT,
    ) -> None:
        self._client = SPARQLClient(sparql_endpoint) if sparql_endpoint else SPARQLClient()
        self._llm = _load_llm()
        self._retrieve = _load_p7(p7_root)

    def query(self, question: str) -> dict[str, Any]:
        """
        Run a GraphRAG query.

        Returns:
            answer              — LLM-synthesised answer grounded in both sources
            graph_context       — formatted graph facts used as context
            retrieved_passages  — text passages from p7 (empty list if unavailable)
            entities_found      — gene names extracted from the question
            retrieval_path      — "fast" | "slow" | "none" (p7 not available)
        """
        accessions = _extract_proteins(question)
        entities = [ACCESSION_MAP.get(a, a) for a in accessions]

        graph_ctx = _sparql_context(self._client, accessions)
        graph_context_str = _format_graph_context(graph_ctx, accessions)

        passages: list[str] = []
        retrieval_path = "none"

        if self._retrieve is not None:
            retrieval_query = question if not entities else f"{' '.join(entities)} {question}"
            p7_result = self._retrieve(retrieval_query)
            passages = [r["text"] for r in p7_result.get("results", [])]
            retrieval_path = p7_result.get("path", "unknown")

        if self._llm is not None:
            answer = _synthesise(question, graph_context_str, passages, self._llm)
        else:
            answer = graph_context_str  # degrade gracefully: return raw graph facts

        return {
            "answer":             answer,
            "graph_context":      graph_context_str,
            "retrieved_passages": passages,
            "entities_found":     entities,
            "retrieval_path":     retrieval_path,
        }
