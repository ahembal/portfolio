# SPE / EHDS — Secure Processing Environment under the European Health Data Space

**Status:** researched
**Target:** p5 (regulatory/compliance doc) + p10 (algorithm-submission framing)
**Opened:** 2026-06-11

## What it is

The European Health Data Space (EHDS) is EU regulation (2025) that requires
health data holders (hospitals, registries, biobanks) to make data available
for secondary use (research, policy, AI development) through a standardised
infrastructure.

The core technical requirement is the Secure Processing Environment (SPE): a
controlled compute environment where researchers submit algorithms rather than
exporting data. Data never leaves the SPE. Results — aggregated outputs,
trained model weights, evaluation metrics — are what researchers receive.

TEHDAS2 (Joint Action on EHDS, phase 2) published the SPE technical
specifications. Key requirements:
- Isolation: no network egress from the compute environment to researcher
  infrastructure during execution
- Audit trail: every access, every job, every result export is logged
- Access control: role-based, tied to data access agreements (DAAs)
- Algorithm submission model: researcher submits a container; SPE runs it
- No raw data export: results go through a statistical disclosure control
  (SDC) check before release
- Pseudonymisation: data is pseudonymised before entering the SPE

## Why it matters for this portfolio

The portfolio includes projects on clinical/biomedical data (p1 medical
imaging, p4 NLP on clinical abstracts, p10 pathology segmentation). All three
would require SPE access in a real production setting under EHDS. Framing the
homelab as an SPE prototype — with honest scope boundaries — connects the
technical infrastructure to a live regulatory requirement and demonstrates
domain awareness beyond the ML layer.

This is especially relevant given the Euro-BioImaging context (the
organisation operates imaging nodes that will fall under EHDS for imaging
data secondary use).

## Connections to existing projects

- **p10 — BEETLE pathology segmentation:** the Grand Challenge submission
  model is architecturally identical to SPE. You submit a Docker container;
  Grand Challenge runs it on data you never see; results are returned. This
  is the algorithm-to-data pattern that EHDS mandates. p10 is the most
  direct SPE analogy in the portfolio.
- **p5 — dev practices / regulatory doc:** the planned EU AI Act doc in p5
  should include an EHDS/SPE section. Projects p1, p4, p10 all fall under
  EHDS secondary use scope.
- **p9 — knowledge graph:** health data catalogues under EHDS need a
  discovery layer. A knowledge graph connecting datasets, variables, and
  access conditions is exactly the kind of infrastructure EHDS HealthData@EU
  mandates. p9 Phase 7 (institutional catalogue) is relevant here.
- **Homelab infrastructure:** Kubernetes namespace isolation, Ceph encrypted
  storage, ArgoCD audit trail, and Tailscale network boundary together
  implement the technical substrate of an SPE. Missing: governance layer
  (DAA enforcement, pseudonymisation pipeline, SDC output review).

## Open questions

- [ ] Does TEHDAS2 spec require a specific technology stack, or is it
      requirements-based (allowing Kubernetes as the isolation layer)?
- [ ] Is there a reference implementation or testbed SPE we could compare
      against?
- [ ] What exactly does "statistical disclosure control" require for model
      weights? (If a model is trained on personal data, is releasing the
      weights considered a data export?)
- [ ] How does this connect to the PUMA challenge / Virchow2 — were those
      models trained under SPE conditions?

## Evidence / research

**2026-06-11** — TEHDAS2 published SPE specifications under EHDS. Reviewed
the core requirements. Key finding: the algorithm-submission model is the
architectural centrepiece. Grand Challenge (p10) implements this pattern
exactly. The homelab covers the compute substrate but not the governance layer
(DAA enforcement, pseudonymisation, SDC). Framing must be honest about that
gap.

**2026-06-11** — Euro-BioImaging operates imaging nodes that will fall under
EHDS for imaging data. p9 Phase 7 institutional catalogue is directly relevant
to the EHDS discovery layer requirement.

## Decision

**Placed (partial):**
- p5 regulatory doc: add EHDS/SPE section covering p1, p4, p10 scope and
  the homelab-as-SPE-substrate framing. Write after p5 EU AI Act section is
  drafted.
- p10 docs: add a note in `docs/gc-submission.md` framing Grand Challenge
  submission as the algorithm-to-data pattern required by EHDS SPEs.
- Open questions above remain unresolved — full placement pending research.
