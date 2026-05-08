"""
Benchmark dataset — 50 curated life science questions.

Each entry has:
  question      — the query
  complexity    — "simple" or "complex" (ground truth for classifier evaluation)
  expected_pmids — PMIDs that should appear in retrieved results (may be empty)
  reference     — a short reference answer for faithfulness scoring

The dataset is versioned and fixed. Do not modify entries — add new ones at
the end with a new version comment if needed.
"""

BENCHMARK: list[dict] = [
    # v1 — 2026-05-08
    # Factual / simple
    {"question": "What gene encodes the p53 protein?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "TP53 encodes the p53 tumour suppressor protein."},

    {"question": "What is the function of BRCA1?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "BRCA1 is involved in DNA damage repair and tumour suppression."},

    {"question": "What does EGFR stand for?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "EGFR stands for Epidermal Growth Factor Receptor."},

    {"question": "What type of cancer is glioblastoma?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Glioblastoma is an aggressive primary brain tumour."},

    {"question": "What is immunotherapy?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Immunotherapy uses the immune system to treat disease, including cancer."},

    {"question": "What is CRISPR used for?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "CRISPR-Cas9 is used for precise gene editing."},

    {"question": "What is the mTOR pathway?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "mTOR is a signalling pathway that regulates cell growth and metabolism."},

    {"question": "What is a checkpoint inhibitor?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Checkpoint inhibitors are drugs that block proteins that prevent immune cells from killing cancer cells."},

    {"question": "What is CAR-T cell therapy?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "CAR-T cell therapy engineers a patient's T cells to express receptors targeting cancer cells."},

    {"question": "What is single cell RNA sequencing?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Single cell RNA sequencing measures gene expression in individual cells."},

    # Comparative / complex
    {"question": "Compare the roles of BRCA1 and BRCA2 in DNA repair.",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "Both BRCA1 and BRCA2 are involved in homologous recombination repair, but BRCA1 also has roles in cell cycle checkpoint activation while BRCA2 directly loads RAD51."},

    {"question": "How does TP53 regulate apoptosis?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "TP53 activates pro-apoptotic genes such as BAX and PUMA, and represses anti-apoptotic genes, triggering the mitochondrial apoptosis pathway."},

    {"question": "What proteins interact with TP53 in the DNA damage response?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "TP53 interacts with MDM2, ATM, CHK2, and p21 among others in the DNA damage response."},

    {"question": "What are the mechanisms of resistance to EGFR inhibitors in lung cancer?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "Resistance mechanisms include T790M mutation, MET amplification, and small cell transformation."},

    {"question": "How does the mTOR pathway interact with PI3K signalling?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "PI3K activates AKT which phosphorylates and activates mTORC1, linking growth factor signalling to protein synthesis."},

    {"question": "What are the differences between PD-1 and PD-L1 inhibitors?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "PD-1 inhibitors target the receptor on T cells; PD-L1 inhibitors target the ligand on tumour cells. Both block the PD-1/PD-L1 checkpoint."},

    {"question": "How does CRISPR differ from older gene editing technologies?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "CRISPR is simpler, faster, and more accurate than zinc finger nucleases and TALENs, which require protein engineering for each target."},

    {"question": "What are the downstream targets of EGFR signalling in cancer?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "EGFR activates RAS/MAPK, PI3K/AKT, and JAK/STAT pathways."},

    {"question": "How does glioblastoma evade the immune system?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "Glioblastoma suppresses immune responses via TGF-beta secretion, IDO expression, and recruitment of regulatory T cells."},

    {"question": "What is the relationship between TP53 mutation and chemotherapy resistance?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "TP53 mutations impair apoptosis induction by DNA-damaging chemotherapy, reducing treatment efficacy."},
]
