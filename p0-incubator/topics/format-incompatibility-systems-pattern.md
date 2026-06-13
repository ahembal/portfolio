# Format Incompatibility as a Systems Pattern

**Status:** raw
**Target:** p10 (WSI format framing) + p5 (cross-cutting systems pattern doc)
**Opened:** 2026-06-13

## What it is

Every data system eventually hits a wall where the format a producer writes
is not the format a consumer can read. This is not a bug — it is a structural
consequence of how standards evolve: vendors ship proprietary formats first,
open standards emerge later, and the industry spends years in the gap between
the two.

### The motivating example: the codec war

iPhones record video in H.265 (.mov) because Apple invented it and it
compresses twice as well as H.264. Chrome, Firefox, and Edge cannot play H.265
because it has patent licensing fees that Google, Mozilla, and Microsoft
refused to pay. Safari plays it fine. The result: a video recorded on an
iPhone cannot be played in Chrome without a conversion step.

Every major platform (YouTube, Instagram, WhatsApp) solves this the same way:
accept any format on upload, transcode server-side to a universally playable
format (H.264), serve the converted file. The user never sees the problem.

The community's long-term answer is AV1 — a royalty-free codec agreed on by
Google, Mozilla, Microsoft, Apple, Netflix, and Amazon. All major browsers
now play AV1. Most phones do not yet record in AV1. The transition is
underway but incomplete. Until it finishes, a transcoding step is still
required.

### The same pattern in medical imaging

Digital pathology scanners each use a proprietary format:

| Vendor | Format |
|--------|--------|
| Aperio (Leica) | `.svs` |
| Hamamatsu | `.ndpi` |
| 3DHistech | `.mrxs` |
| Leica | `.scn` |
| Generic | `.tif` (many dialects) |

DICOM is the official standard for medical images — like AV1 for video. In
practice, whole slide images (WSIs) are rarely stored as DICOM because the
vendors shipped their formats years before DICOM extensions for WSI were
finalised. Researchers end up with a mix of scanner-specific files and rely
on OpenSlide (a compatibility library) to bridge them — exactly as a
transcoding pipeline bridges video formats.

p10 (BEETLE pathology segmentation) handles this via TIAToolbox, which uses
OpenSlide underneath. The `WSI_SUFFIXES` set in `data/pipeline.py` is a
direct acknowledgement of the problem: you cannot assume a single format.

### Other instances in this portfolio

- **p9 — RDF serialisation:** the same graph can be serialised as Turtle,
  JSON-LD, N-Triples, or RDF/XML. Different tools expect different formats.
  The builder serialises to Turtle because Fuseki's bulk loader prefers it,
  not because Turtle is universally better.
- **p4 — clinical text encoding:** clinical text comes from different HIS
  vendors with different character encodings, field delimiters, and
  abbreviation conventions. The preprocessing step is a format bridge.
- **p8 — model formats:** ONNX exists precisely because every framework
  (PyTorch, TensorFlow, JAX) uses a different model serialisation format.
  ONNX is the AV1 of ML models — an open standard the whole industry agreed
  on, with varying degrees of adoption.

## The general pattern

In every case, the structure is the same:

```
Producer (proprietary format)
    ↓
Compatibility layer / transcoding step
    ↓
Consumer (expects a different format)
```

The compatibility layer is the tax. It adds latency, storage cost, and
operational complexity. The industry tries to eliminate it by converging on
open standards, but the convergence is always slower than the vendor
innovation that created the fragmentation in the first place.

The architectural lesson: when designing a system that ingests data from
multiple sources, plan for format diversity from the start. The question
is not "will I encounter incompatible formats?" but "where will I put the
conversion step, and how will I make it observable when it fails?"

## Why it matters for this portfolio

The portfolio already demonstrates this pattern in three places (p8 ONNX,
p9 Turtle, p10 TIAToolbox/OpenSlide) without naming it. Naming it — in p5
or in a cross-cutting doc — turns three separate implementation details into
one coherent design principle.

It also adds context to p10's format handling: the `WSI_SUFFIXES` set and
TIAToolbox choice are not arbitrary — they are the correct response to a
known industry-wide fragmentation problem.

## Connections to existing projects

- **p10 — BEETLE segmentation:** primary application. WSI format diversity
  is the direct instance of this pattern. Worth a paragraph in
  `docs/data-pipeline.md` explaining why TIAToolbox was chosen.
- **p8 — model registry:** ONNX as the open standard that bridges PyTorch
  and inference runtimes. The benchmark demonstrates the value of the bridge.
- **p9 — knowledge graph:** RDF serialisation choice. Secondary.
- **p5 — dev practices:** the pattern itself as a cross-cutting systems doc.
- **Cross-cutting docs topic (`cross-cutting-docs.md`):** this pattern would
  fit naturally in a `docs/interoperability.md` at repo root.

## Open questions

- [ ] Is there a compelling standalone project here, or is this only worth
      documenting as a pattern across existing projects?
- [ ] Would a small demo — a format-agnostic ingestion pipeline that accepts
      WSI, video, and RDF and normalises each — be useful, or is it a toy?
- [ ] DICOM for WSI: is adoption actually improving? If hospitals are moving
      to DICOM WSI storage, p10's TIAToolbox approach may need updating.
- [ ] AV1 encoding on phones: what is the current adoption? This determines
      when the codec war is effectively over.

## Evidence / research

**2026-06-13** — Conversation about HEIC image and MOV video incompatibility
on a web app. Root cause: H.265 patent licensing fees → Chrome never shipped
H.265 decoding → iPhone videos (.mov, H.265) do not play in Chrome.
Community solution: AV1 (royalty-free, all browsers support playback, phone
recording support still rolling out). Immediate practical solution: server-side
transcoding (Cloudflare Stream).

**2026-06-13** — Recognised same structural pattern in p10 WSI format
diversity, p8 ONNX, p9 RDF serialisation. The codec war is the most vivid
illustration of a pattern that appears throughout the portfolio.

## Decision

<!-- Pending. The most actionable near-term step is a paragraph in p10's
     data-pipeline.md explaining the WSI format fragmentation problem and
     why TIAToolbox/OpenSlide is the right compatibility layer. The broader
     pattern doc belongs in cross-cutting-docs once READMEs are done. -->
