# GraphRAG Synthesis Prompt Engineering
*p9 — Knowledge Graph & Semantic Search*

---

This document records how the GraphRAG synthesis prompt was designed and
iterated. The prompt governs how the LLM combines graph facts with retrieved
passages into a final answer. Each iteration is shown with the problem it
solved and the output change it produced.

---

## The role of the synthesis prompt in GraphRAG

GraphRAG assembles two sources of context before calling the LLM:

1. **Graph facts** — structured, exact: paper titles, co-mention counts,
   protein function annotations, disease annotations (from Fuseki via SPARQL)
2. **Retrieved passages** — unstructured text from p7 ChromaDB

The synthesis prompt is the instruction that tells the LLM how to combine
these two sources into a coherent answer. Getting it wrong means the LLM
either ignores one source, uses the wrong framing, or produces a shallow
response despite having rich context.

---

## Iteration 1 — Baseline

**Prompt:**
```
You are a biomedical research assistant. Answer the question using ONLY the
information provided below. Do not add knowledge not present in the sources.

Question: {question}

Graph facts (structured, exact):
{graph_context}

Retrieved passages (unstructured text):
{passages_text}

Answer:
```

**Test question:**
*Which proteins are mentioned in BRCA1 papers, and what do we know about
their function?*

**Output:**
```
Based on the provided information, the following proteins are mentioned in
BRCA1 papers:

1. PALB2 — an integral component of the BRCA complex required for
   homologous recombination repair.

Additionally, BRCA2 is frequently co-mentioned with BRCA1 in 17 papers,
but it's not clear how they interact or what we know about their joint
function.
```

**Problems identified:**

1. The LLM listed only PALB2, ignoring 9 other proteins in the graph context.
2. It said "it's not clear how they interact" for BRCA2 — despite the graph
   containing a full UniProt function annotation for BRCA2.
3. The graph context included 14 function annotations; the LLM used 1.

**Root cause:** The baseline prompt gave no instruction about how to use the
graph context. The LLM defaulted to surface-level reading rather than
systematically working through all entries.

---

## Iteration 2 — Explicit instruction to use all graph facts

**Change:** Added explicit instruction to use all protein function entries
and to answer each part of the question explicitly.

```
Use ALL relevant facts from the graph — especially the protein functions listed.
...
Answer each part of the question explicitly. If proteins and their functions
are both in the graph, list each protein with its function:
```

**Output:**
```
* BRCA2 (shared in 17 papers): Involved in double-strand break repair
  and/or homologous recombination...
* PALB2 (shared in 9 papers): [2009] PALB2 is an integral component of
  the BRCA complex...
* ATM (shared in 6 papers): Serine/threonine protein kinase...
* TP53 (shared in 4 papers): Multifunctional transcription factor...
* RB1 (shared in 6 papers): Tumor suppressor...

These proteins are mentioned in BRCA1 papers and their functions provide
insights into their roles in DNA repair and cancer susceptibility.
```

**Problems identified:**

1. "associated with BRCA1" — the graph records paper co-occurrence, not
   direct biological association. This is a precision error: the graph
   does not assert that BRCA2 interacts with BRCA1, only that they appear
   in the same papers.
2. PALB2 was pulled from a paper title (*"PALB2 is an integral component..."*)
   rather than a UniProt function annotation. The citation marker `[2009]`
   in the output reveals this — it came from the paper list, not the
   functions section. After iteration 3, PALB2 was correctly dropped from
   the function list because it has no UniProt function annotation in the
   graph.
3. The closing sentence ("insights into their roles in DNA repair and cancer
   susceptibility") was too narrow — the proteins span DNA repair, checkpoint
   signalling, cell-cycle control, transcriptional regulation, and oncogenic
   signalling.

---

## Iteration 3 — Framing rules for co-occurrence vs association

**Change:** Added two explicit framing rules to the prompt.

```
Important framing rules:
- The graph records which proteins co-occur in the same papers. Say
  "co-mentioned with X in the papers represented in the graph" — not
  "associated with X", which implies a direct biological relationship
  the graph does not assert.
- When listing proteins with their functions, end with a single broad
  sentence covering the shared biological themes (e.g. DNA repair,
  checkpoint signalling, cell-cycle control, cancer pathways) rather
  than restating one specific mechanism.
```

**Output:**
```
1. BRCA2: Involved in double-strand break repair and/or homologous
   recombination.
2. APC: Tumor suppressor that promotes rapid degradation of CTNNB1
   and participates in Wnt signaling as a negative regulator.
3. RB1: Key regulator of the G1/S transition of the cell cycle...
4. ATM: Serine/threonine protein kinase that activates checkpoint
   signaling upon double strand breaks...
5. EGFR: Receptor tyrosine kinase binding ligands of the EGF family...
6. TP53: Multifunctional transcription factor that induces cell cycle
   arrest, DNA repair or apoptosis...
7. MDM2: E3 ubiquitin-protein ligase that mediates ubiquitination of
   p53/TP53...
8. KRAS: Plays an important role in the regulation of cell
   proliferation...
9. PTEN: Dual-specificity protein phosphatase...

These proteins are related to DNA repair (BRCA2, ATM), cell cycle
regulation (RB1), tumor suppression (APC, BRCA2), checkpoint signaling
(ATM), transcriptional regulation (TP53), protein degradation (MDM2),
and cell proliferation (KRAS, EGFR).
```

**Result:** All 9 proteins with UniProt function annotations listed.
PALB2 correctly absent (no function annotation in graph — only a paper
title). Closing sentence covers all biological themes. Framing is precise
about what the graph actually represents.

---

## Lessons

**Tell the LLM what structure to follow, not just what to avoid.**
"Do not add knowledge not present in the sources" prevents hallucination
but does not tell the LLM how to use what IS there. Explicit structure
instructions ("list each protein with its function") produced a much more
complete answer.

**Precision of language matters in prompts about data.**
"Associated with" and "co-mentioned in the same papers" are not equivalent.
The graph asserts co-occurrence, not biological interaction. Making this
distinction explicit in the prompt produced the correct framing in the output.

**The closing sentence needs a scope instruction.**
Without guidance, the LLM closed with the most salient theme it saw (DNA
repair). With an instruction to cover broad shared themes, it produced a
sentence that accurately summarised all nine proteins' functional domains.

**Source provenance affects answer quality.**
PALB2 appeared in iteration 2 because the LLM read a paper title as a
functional description. Once the graph context separated paper titles from
function annotations clearly, and the prompt told the LLM to use function
annotations specifically, the provenance distinction resolved itself.
