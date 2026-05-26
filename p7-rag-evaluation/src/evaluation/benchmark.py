"""
Benchmark dataset — 50 curated life science questions.

Each entry has:
  question       — the query
  complexity     — "simple" or "complex" (ground truth for classifier evaluation)
  expected_pmids — PMIDs that should appear in retrieved results (may be empty)
  reference      — a short reference answer for faithfulness scoring

The dataset is versioned and fixed. Do not modify entries — add new ones at
the end with a new version comment if needed.

Version history:
  v1 (2026-05-08): 20 questions (10 simple, 10 complex)
  v2 (2026-05-26): 50 questions — added 15 simple, 15 complex
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

    # v2 — 2026-05-26
    # Simple — additional factual questions
    {"question": "What does KRAS stand for?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "KRAS stands for Kirsten RAS, named after the Kirsten sarcoma retrovirus."},

    {"question": "What is a tumour suppressor gene?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "A tumour suppressor gene encodes a protein that inhibits cell proliferation or promotes apoptosis; loss of function promotes cancer."},

    {"question": "What is HER2 and why is it important in breast cancer?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "HER2 (ERBB2) is a receptor tyrosine kinase amplified in ~20% of breast cancers, predicting response to trastuzumab (Herceptin)."},

    {"question": "What is liquid biopsy?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Liquid biopsy detects circulating tumour DNA, cells, or exosomes in blood to assess tumour mutations and monitor treatment response without tissue biopsy."},

    {"question": "What is the function of ATM kinase?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "ATM kinase is activated by DNA double-strand breaks and coordinates the DNA damage response by phosphorylating substrates including H2AX, BRCA1, and TP53."},

    {"question": "What is the retinoblastoma protein?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "The retinoblastoma protein (pRb), encoded by RB1, is a tumour suppressor that regulates the G1-to-S cell cycle transition by inhibiting E2F transcription factors."},

    {"question": "What is synthetic lethality?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Synthetic lethality occurs when simultaneous loss of two genes is lethal to a cell, but loss of either alone is not; exploited therapeutically to target tumours with specific mutations."},

    {"question": "What is whole genome sequencing?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Whole genome sequencing determines the complete DNA sequence of an organism's genome, enabling detection of all variants including SNVs, indels, and structural alterations."},

    {"question": "What is spatial transcriptomics?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Spatial transcriptomics measures gene expression while preserving the spatial location of cells within tissue, combining transcriptomics with histological context."},

    {"question": "What is MDM2?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "MDM2 is an E3 ubiquitin ligase and the principal negative regulator of TP53; it binds TP53, inhibits its activity, and targets it for proteasomal degradation."},

    {"question": "What is a driver mutation?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "A driver mutation confers a selective growth advantage to a cell and contributes causally to cancer development, as opposed to passenger mutations that are neutral."},

    {"question": "What is PALB2?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "PALB2 (partner and localiser of BRCA2) bridges BRCA1 and BRCA2 in homologous recombination repair; germline variants increase breast and ovarian cancer risk."},

    {"question": "What is tumour mutational burden?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "Tumour mutational burden (TMB) is the number of somatic mutations per megabase in a tumour genome; high TMB correlates with response to immune checkpoint inhibitors."},

    {"question": "What is the PI3K-AKT pathway?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "The PI3K-AKT pathway transmits growth factor signals to promote cell survival, proliferation, and metabolism; frequently activated by mutation in cancer."},

    {"question": "What is PARP and why is it a cancer drug target?",
     "complexity": "simple",
     "expected_pmids": [],
     "reference": "PARP (poly ADP-ribose polymerase) repairs single-strand DNA breaks; PARP inhibitors exploit synthetic lethality in BRCA1/2-deficient tumours that cannot repair double-strand breaks."},

    # Complex — additional multi-hop questions
    {"question": "How do KRAS mutations affect response to EGFR-targeted therapy in colorectal cancer?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "KRAS mutations activate downstream RAS/MAPK signalling independently of EGFR, rendering anti-EGFR antibodies such as cetuximab ineffective; KRAS testing is mandatory before prescribing these agents."},

    {"question": "How does MDM2 regulate TP53 and what are the therapeutic implications?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "MDM2 binds and ubiquitinates TP53, targeting it for degradation. In tumours with MDM2 amplification and wild-type TP53, MDM2 inhibitors (nutlins) reactivate p53 tumour suppression."},

    {"question": "What is the relationship between ATM and TP53 in the DNA damage response?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "ATM activates TP53 indirectly by phosphorylating and activating CHK2, which in turn phosphorylates TP53 at Ser20, preventing MDM2 binding and stabilising TP53 to drive cell cycle arrest or apoptosis."},

    {"question": "How do PARP inhibitors exploit BRCA1/2 deficiency?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "BRCA1/2-deficient cells cannot perform homologous recombination. PARP inhibitors block single-strand break repair, forcing lesions into double-strand breaks that cannot be repaired — synthetic lethality kills only the BRCA-deficient cells."},

    {"question": "What are the clinical differences between BRCA1- and BRCA2-associated breast cancers?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "BRCA1-associated cancers are more often triple-negative and high-grade; BRCA2-associated cancers are more often ER-positive. Both are sensitive to PARP inhibitors and platinum chemotherapy, but BRCA2 also elevates male breast and prostate cancer risk."},

    {"question": "How does the RB1 pathway control the G1-to-S transition and how is it disrupted in cancer?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "Hypophosphorylated pRb binds E2F transcription factors, blocking S-phase genes. CDK4/6-cyclin D phosphorylates pRb, releasing E2F. In cancer, RB1 deletion, CDK4/6 amplification, or cyclin D overexpression constitutively inactivate pRb."},

    {"question": "What is the role of PALB2 in the BRCA1-BRCA2 complex and what happens when it is lost?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "PALB2 physically bridges BRCA1 and BRCA2 in the nucleus, enabling BRCA2 to load RAD51 at double-strand break sites. PALB2 loss disrupts this complex, impairing homologous recombination similarly to BRCA1/2 loss and conferring PARP inhibitor sensitivity."},

    {"question": "How do CDK4/6 inhibitors restore RB1 tumour suppression?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "CDK4/6 inhibitors block CDK4/6-cyclin D from phosphorylating pRb, keeping it in the active hypophosphorylated state that suppresses E2F. This is only effective in tumours with intact RB1; RB1-null tumours are intrinsically resistant."},

    {"question": "What distinguishes triple-negative breast cancer from other breast cancer subtypes in terms of treatment options?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "Triple-negative breast cancer lacks ER, PR, and HER2 — making hormonal therapy and HER2-targeted agents ineffective. Treatment relies on chemotherapy; BRCA-mutant TNBC responds to PARP inhibitors; PD-L1-positive TNBC responds to immunotherapy."},

    {"question": "How do immune checkpoint inhibitors differ mechanistically from targeted therapies like EGFR inhibitors?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "Targeted therapies directly inhibit a driver oncogene (e.g. mutant EGFR). Checkpoint inhibitors (anti-PD-1, anti-CTLA-4) act on the immune system, releasing inhibitory signals that prevent T cells from recognising and killing tumour cells — they are not tumour-cell-specific."},

    {"question": "What are the challenges of directly targeting RAS oncoproteins and how has KRAS G12C changed this?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "RAS lacks a defined drug-binding pocket and has picomolar affinity for GTP, making competitive inhibition impractical. The KRAS G12C cysteine creates a unique reactive site: covalent inhibitors (sotorasib, adagrasib) lock G12C in the inactive GDP-bound state, the first direct RAS inhibition to reach clinical approval."},

    {"question": "How does ATM loss contribute to cancer predisposition and genomic instability?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "ATM loss impairs the DNA damage checkpoint — cells with DNA double-strand breaks continue cycling rather than arresting, accumulating mutations and chromosomal aberrations. This drives genomic instability and increases cancer risk, particularly leukaemia, lymphoma, and breast cancer in heterozygotes."},

    {"question": "Compare BM25 and dense vector retrieval for biomedical question answering.",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "BM25 is a term-frequency model excelling at exact keyword matches (gene names, drug names, PMIDs); it fails on synonyms. Dense retrieval encodes semantic meaning and finds relevant passages even without exact term overlap but requires a domain-appropriate encoder. Hybrid search combining both outperforms either alone on biomedical benchmarks."},

    {"question": "How does the BRCA1-PALB2-BRCA2 axis coordinate homologous recombination repair?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "BRCA1 recruits PALB2 to DNA damage sites via a direct coiled-coil interaction. PALB2 in turn binds BRCA2, which loads RAD51 onto single-stranded DNA for strand invasion. Loss of any node in this axis disrupts RAD51 loading and homologous recombination."},

    {"question": "Why does TP53 mutation status predict different outcomes for MDM2 inhibitor therapy versus chemotherapy?",
     "complexity": "complex",
     "expected_pmids": [],
     "reference": "MDM2 inhibitors reactivate p53 by blocking MDM2 binding — they are only effective in TP53 wild-type tumours. Chemotherapy induces DNA damage to trigger p53-dependent apoptosis; TP53 mutations impair this response. The two therapies therefore require opposite TP53 selection criteria."},
]
