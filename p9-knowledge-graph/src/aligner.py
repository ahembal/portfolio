"""
EDAM / OBI ontology alignment for p9.

Adds ontology-aligned triples to the knowledge graph so local entities
are interoperable with external datasets that use EDAM and OBI terms.

What gets aligned:
  Paper   → edam:has_topic   <EDAM topic term>   (keyword-based, from title)
  Protein → rdf:type         edam:data_0896       (Protein report)
  Disease → edam:has_topic   edam:topic_0634      (Pathology)
  Author  → rdf:type         obi:0000070          (skipped — OBI targets assays,
                                                    not agents; kept for extension)

Usage:
    from src.aligner import align
    enriched_graph = align(graph)
"""

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

P9   = Namespace("http://portfolio/p9/")
SCH  = Namespace("https://schema.org/")
EDAM = Namespace("http://edamontology.org/")
UP   = Namespace("http://purl.uniprot.org/core/")

# EDAM topic terms used for paper alignment
EDAM_TOPICS: dict[str, URIRef] = {
    "oncology":     EDAM["topic_2640"],  # Oncology
    "genomics":     EDAM["topic_0622"],  # Genomics
    "proteomics":   EDAM["topic_0121"],  # Proteomics
    "pathways":     EDAM["topic_0602"],  # Molecular interactions, pathways and networks
    "transcriptomics": EDAM["topic_3308"],  # Transcriptomics
    "sequencing":   EDAM["topic_3168"],  # Sequencing
    "medicine":     EDAM["topic_3303"],  # Medicine
    "dna_repair":   EDAM["topic_3673"],  # Whole genome sequencing (closest EDAM to repair)
}

# Keyword → EDAM topic mapping; order matters (first match wins per keyword group)
KEYWORD_MAP: list[tuple[list[str], URIRef]] = [
    (["cancer", "tumor", "tumour", "oncol", "carcinoma", "neoplasm", "malignant"],
     EDAM["topic_2640"]),
    (["dna repair", "dna damage", "double strand break", "mismatch repair", "nucleotide excision"],
     EDAM["topic_3299"]),  # DNA repair mapped to topic_3299 (Sequence analysis, closest available)
    (["signall", "pathway", "kinase", "receptor", "phosphorylation"],
     EDAM["topic_0602"]),
    (["gene express", "transcri", "mrna", "rna-seq"],
     EDAM["topic_3308"]),
    (["protein", "proteom", "peptide"],
     EDAM["topic_0121"]),
    (["sequen", "genome", "genomic", "variant", "mutation", "snp"],
     EDAM["topic_0622"]),
    (["medicine", "clinical", "patient", "therapy", "treatment", "drug"],
     EDAM["topic_3303"]),
]

# EDAM data types for entity alignment
EDAM_PROTEIN_REPORT = EDAM["data_0896"]   # Protein report
EDAM_DISEASE_TOPIC  = EDAM["topic_0634"]  # Pathology


def _topic_for_title(title: str) -> URIRef | None:
    t = title.lower()
    for keywords, topic_uri in KEYWORD_MAP:
        if any(kw in t for kw in keywords):
            return topic_uri
    return None


def align(g: Graph) -> Graph:
    """
    Add EDAM/OBI alignment triples to g in-place and return g.

    Papers get edam:has_topic based on title keyword matching.
    Proteins (both p9:Protein and up:Protein) get rdf:type edam:data_0896.
    Diseases get edam:has_topic edam:topic_3324 (Pathology).
    """
    g.bind("edam", EDAM)

    _align_papers(g)
    _align_proteins(g)
    _align_diseases(g)

    return g


def _align_papers(g: Graph) -> None:
    for paper in list(g.subjects(RDF.type, P9.Paper)):
        title = next((str(o) for o in g.objects(paper, SCH.name)), "")
        topic = _topic_for_title(title)
        if topic:
            g.add((paper, EDAM.has_topic, topic))


def _align_proteins(g: Graph) -> None:
    for protein in set(g.subjects(RDF.type, UP.Protein)) | set(g.subjects(RDF.type, P9.Protein)):
        g.add((protein, RDF.type, EDAM_PROTEIN_REPORT))


def _align_diseases(g: Graph) -> None:
    for disease in list(g.subjects(RDF.type, P9.Disease)):
        g.add((disease, EDAM.has_topic, EDAM_DISEASE_TOPIC))
