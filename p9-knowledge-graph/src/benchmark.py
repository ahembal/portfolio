"""
Benchmark dataset — 20 questions for RAG vs SPARQL comparison.

Split:
  10 structured   — set intersection, counting, multi-hop traversal.
                    Favour SPARQL; RAG is expected to struggle or hallucinate.
  10 open-ended   — explanation, synthesis, analogical reasoning.
                    Favour RAG; SPARQL cannot generate prose answers.

Each entry:
  question        natural language question
  type            "structured" | "open_ended"
  sparql          SPARQL SELECT query (structured questions only)
  reference       description of the expected correct answer — used by the
                  judge to score both systems
  expected_shape  what the ideal answer looks like: "count", "list", "prose"

Ground truth for structured questions is the SPARQL result itself.
RAG answers are compared against the SPARQL result by the judge.
SPARQL is not run against open-ended questions (it cannot synthesise prose).
"""

BENCHMARK: list[dict] = [
    # ── Structured questions (SPARQL favoured) ────────────────────────────────

    {
        "question": "How many papers in the dataset mention TP53?",
        "type": "structured",
        "expected_shape": "count",
        "reference": "An exact integer count of papers with a p9:mentions edge to the TP53 protein.",
        "sparql": """\
SELECT (COUNT(DISTINCT ?paper) AS ?count) WHERE {
  ?paper a p9:Paper ;
         p9:mentions uprot:P04637 .
}""",
    },

    {
        "question": "Which papers mention both TP53 and BRCA1?",
        "type": "structured",
        "expected_shape": "list",
        "reference": "The set of paper titles (and PMIDs) whose paper nodes have p9:mentions edges to both P04637 and P38398.",
        "sparql": """\
SELECT ?paper ?title WHERE {
  ?paper a p9:Paper ;
         schema:name ?title ;
         p9:mentions uprot:P04637 ;
         p9:mentions uprot:P38398 .
}
ORDER BY ?title""",
    },

    {
        "question": "Which proteins are mentioned in more than 5 papers?",
        "type": "structured",
        "expected_shape": "list",
        "reference": "UniProt accessions (and their paper counts) for proteins with more than 5 p9:mentions edges from papers.",
        "sparql": """\
SELECT ?protein (COUNT(DISTINCT ?paper) AS ?n) WHERE {
  ?paper a p9:Paper ;
         p9:mentions ?protein .
}
GROUP BY ?protein
HAVING (COUNT(DISTINCT ?paper) > 5)
ORDER BY DESC(?n)""",
    },

    {
        "question": "Which papers mentioning EGFR were published after 2018?",
        "type": "structured",
        "expected_shape": "list",
        "reference": "Titles and publication years of papers with p9:mentions to EGFR (P00533) and schema:datePublished > 2018.",
        "sparql": """\
SELECT ?paper ?title ?year WHERE {
  ?paper a p9:Paper ;
         schema:name ?title ;
         schema:datePublished ?year ;
         p9:mentions uprot:P00533 .
  FILTER(xsd:integer(?year) > 2018)
}
ORDER BY DESC(?year)""",
    },

    {
        "question": "Which proteins are co-mentioned with TP53 in at least 3 papers?",
        "type": "structured",
        "expected_shape": "list",
        "reference": "Proteins that share at least 3 papers with TP53 via p9:mentions edges (excluding TP53 itself).",
        "sparql": """\
SELECT ?other (COUNT(DISTINCT ?paper) AS ?shared) WHERE {
  ?paper a p9:Paper ;
         p9:mentions uprot:P04637 ;
         p9:mentions ?other .
  FILTER(?other != uprot:P04637)
}
GROUP BY ?other
HAVING (COUNT(DISTINCT ?paper) >= 3)
ORDER BY DESC(?shared)""",
    },

    {
        "question": "Which authors have published papers that mention KRAS?",
        "type": "structured",
        "expected_shape": "list",
        "reference": "Author names (and paper counts) of authors whose papers have a p9:mentions edge to KRAS (P01116).",
        "sparql": """\
SELECT ?authorName (COUNT(DISTINCT ?paper) AS ?papers) WHERE {
  ?paper  a             p9:Paper ;
          schema:author ?author ;
          p9:mentions   uprot:P01116 .
  ?author schema:name  ?authorName .
}
GROUP BY ?authorName
ORDER BY DESC(?papers)
LIMIT 20""",
    },

    {
        "question": "List all diseases associated with proteins mentioned by BRCA1-related papers.",
        "type": "structured",
        "expected_shape": "list",
        "reference": "Disease names reachable via: paper → p9:mentions → protein → up:annotation → up:Disease_Annotation → disease, where the paper also mentions BRCA1.",
        "sparql": """\
SELECT DISTINCT ?disease WHERE {
  ?paper    a              p9:Paper ;
            p9:mentions    uprot:P38398 ;
            p9:mentions    ?protein .
  ?protein  up:annotation  ?ann .
  ?ann      a              up:Disease_Annotation ;
            up:disease     ?diseaseRef .
  ?diseaseRef rdfs:label   ?disease .
  FILTER(?protein != uprot:P38398)
}
ORDER BY ?disease""",
    },

    {
        "question": "Which paper in the dataset mentions the most distinct proteins?",
        "type": "structured",
        "expected_shape": "list",
        "reference": "The paper with the highest number of distinct p9:mentions edges, with its title and protein count.",
        "sparql": """\
SELECT ?paper ?title (COUNT(DISTINCT ?protein) AS ?proteinCount) WHERE {
  ?paper a p9:Paper ;
         schema:name ?title ;
         p9:mentions ?protein .
}
GROUP BY ?paper ?title
ORDER BY DESC(?proteinCount)
LIMIT 5""",
    },

    {
        "question": "Which papers are tagged with the oncology EDAM topic?",
        "type": "structured",
        "expected_shape": "list",
        "reference": "Papers that have edam:has_topic edam:topic_2640 (Oncology), added by aligner.py from title keyword matching.",
        "sparql": """\
SELECT ?paper ?title ?year WHERE {
  ?paper a p9:Paper ;
         schema:name ?title ;
         schema:datePublished ?year ;
         edam:has_topic edam:topic_2640 .
}
ORDER BY DESC(?year)""",
    },

    {
        "question": "Which papers mention both MDM2 and TP53?",
        "type": "structured",
        "expected_shape": "list",
        "reference": "Papers with p9:mentions edges to both MDM2 (Q00987) and TP53 (P04637).",
        "sparql": """\
SELECT ?paper ?title ?year WHERE {
  ?paper a p9:Paper ;
         schema:name ?title ;
         schema:datePublished ?year ;
         p9:mentions uprot:Q00987 ;
         p9:mentions uprot:P04637 .
}
ORDER BY DESC(?year)""",
    },

    # ── Open-ended questions (RAG favoured) ───────────────────────────────────

    {
        "question": "What is the role of TP53 in the DNA damage response?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "TP53 acts as a transcription factor activated by DNA damage. "
            "It induces cell cycle arrest (via p21/CDKN1A), DNA repair, and apoptosis "
            "(via BAX, PUMA). MDM2 regulates TP53 stability through ubiquitin-mediated "
            "degradation. Loss of TP53 function is the most common alteration in human cancer."
        ),
        "sparql": None,
    },

    {
        "question": "How does BRCA1 contribute to tumour suppression?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "BRCA1 is a tumour suppressor involved in homologous recombination repair of "
            "double-strand DNA breaks. It forms complexes with BARD1 and interacts with "
            "RAD51. Germline mutations in BRCA1 confer elevated risk of breast and ovarian "
            "cancer. BRCA1 also participates in cell cycle checkpoint activation via ATM/CHK2."
        ),
        "sparql": None,
    },

    {
        "question": "What are the mechanisms by which EGFR drives cancer progression?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "EGFR (HER1) is a receptor tyrosine kinase that activates RAS/MAPK, PI3K/AKT, "
            "and JAK/STAT pathways upon ligand binding. Activating mutations (e.g. L858R in "
            "exon 21) or amplification lead to constitutive signalling, promoting proliferation, "
            "survival, and invasion. EGFR is targeted by TKIs (erlotinib, gefitinib) and "
            "antibodies (cetuximab) in lung and colorectal cancer."
        ),
        "sparql": None,
    },

    {
        "question": "How does PTEN loss affect cancer cell survival?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "PTEN is a phosphatase that degrades PIP3, the product of PI3K. Loss of PTEN "
            "leads to constitutive activation of AKT/mTOR signalling, promoting cell survival, "
            "proliferation, and resistance to apoptosis. PTEN loss is common in glioblastoma, "
            "prostate cancer, and endometrial cancer."
        ),
        "sparql": None,
    },

    {
        "question": "What is the relationship between MDM2 and TP53, and how is it exploited therapeutically?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "MDM2 is the primary negative regulator of TP53. It binds TP53's transactivation "
            "domain, inhibiting transcriptional activity and targeting it for proteasomal "
            "degradation. In tumours with wild-type TP53, MDM2 is frequently amplified. "
            "MDM2 inhibitors (e.g. nutlin-3, RG7112) disrupt this interaction to restore "
            "TP53 activity — a therapeutic strategy in TP53 wild-type cancers."
        ),
        "sparql": None,
    },

    {
        "question": "How does ATM function as a DNA damage sensor and what happens when it is lost?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "ATM is a serine/threonine kinase activated by double-strand breaks. It "
            "phosphorylates H2AX, CHK2, and TP53, coordinating DNA repair and cell cycle "
            "checkpoints. Biallelic loss of ATM causes ataxia-telangiectasia; monoallelic "
            "loss increases cancer susceptibility. ATM-deficient tumours show sensitivity to "
            "PARP inhibitors and DNA-damaging agents."
        ),
        "sparql": None,
    },

    {
        "question": "What cancer types are most frequently associated with KRAS mutations and why?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "KRAS mutations are most common in pancreatic ductal adenocarcinoma (~90%), "
            "colorectal cancer (~40%), and non-small cell lung cancer (~30%). KRAS is a "
            "GTPase; oncogenic mutations (G12D, G12V, G12C) impair GTP hydrolysis, leading "
            "to constitutive RAS/MAPK signalling. KRAS G12C is now targetable with "
            "covalent inhibitors (sotorasib, adagrasib)."
        ),
        "sparql": None,
    },

    {
        "question": "What therapeutic strategies exploit BRCA1 or BRCA2 deficiency?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "BRCA1/2-deficient tumours are impaired in homologous recombination. PARP "
            "inhibitors (olaparib, rucaparib) exploit synthetic lethality: when PARP-mediated "
            "single-strand repair is also blocked, replication forks collapse and cells die. "
            "Platinum chemotherapy also preferentially damages BRCA-deficient cells. "
            "Olaparib is approved for BRCA-mutant breast, ovarian, and pancreatic cancers."
        ),
        "sparql": None,
    },

    {
        "question": "How does EGFR signalling differ between lung cancer and colorectal cancer?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "In lung adenocarcinoma, EGFR is frequently mutated (exon 19 deletions, L858R) "
            "and TKIs are first-line treatment. In colorectal cancer, EGFR is rarely mutated "
            "but often overexpressed; anti-EGFR antibodies (cetuximab) are used but only in "
            "RAS/RAF wild-type tumours. KRAS/NRAS mutations predict resistance to EGFR "
            "antibodies in colorectal cancer but not to TKIs in lung cancer."
        ),
        "sparql": None,
    },

    {
        "question": "What is the clinical significance of RB1 loss in cancer?",
        "type": "open_ended",
        "expected_shape": "prose",
        "reference": (
            "RB1 encodes the retinoblastoma protein, which restrains cell cycle entry by "
            "repressing E2F transcription factors. Loss of RB1 is the defining event in "
            "hereditary retinoblastoma and is found in small cell lung cancer, osteosarcoma, "
            "and bladder cancer. RB1-deficient tumours show altered sensitivity to CDK4/6 "
            "inhibitors and may activate compensatory survival pathways."
        ),
        "sparql": None,
    },
]
