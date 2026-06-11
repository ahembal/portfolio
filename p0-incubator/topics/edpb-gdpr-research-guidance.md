# EDPB Guidance — GDPR Applied to Scientific Research

**Status:** raw
**Target:** p5 (regulatory/compliance doc) + p9 (knowledge graph metadata layer)
**Opened:** 2026-06-11

## What it is

EDPB (European Data Protection Board) published guidance on 15 April 2026
clarifying how GDPR applies to scientific research using personal data. This
is a public consultation draft — not final law — but it is the authoritative
interpretation of what GDPR's research exemptions require in practice.

The document resolves a long-standing ambiguity: GDPR gives research special
treatment, but hospitals, universities, infrastructure providers, and companies
have interpreted those exceptions inconsistently. The guidance says:

> Research may receive special GDPR treatment, but only if it is genuinely
> scientific and properly governed.

## Key practical points (condensed)

**What qualifies as scientific research:**
The work must be systematic, ethical, verifiable, sufficiently independent,
intended to create knowledge, and carried out by qualified people. Not every
data-analysis project qualifies.

**Reuse without purpose-compatibility test:**
Existing personal data may often be reused for research without the usual
purpose-compatibility test. But reuse still needs a valid legal basis and
safeguards — it is not blanket permission.

**Longer retention is accepted:**
Data may be retained beyond the original project when future scientific use is
reasonably expected. Deletion is not automatic.

**Broad consent is formalised:**
Participants may consent to a field of research even when future projects are
unknown. Dynamic consent (participants receive more specific choices later) is
also supported. Additional ethical and technical safeguards are required.

**Legal basis options:**
Consent is not the only basis. Public interest authority and legitimate
interests may support research, including by private or commercial
organisations. Health, genetic, and biometric data (Article 9) still require
an additional condition under EU/national law or explicit consent.

**Ongoing transparency:**
Transparency is not a one-time information sheet. Material changes to
long-running research may require updated information to participants.

**Right to deletion is not absolute:**
A deletion request can be refused where it would make the research impossible
or seriously impair it — but only when data are necessary and appropriate
safeguards exist.

**Consortium responsibilities must be explicit:**
Hospitals, universities, companies, research infrastructures, and IT providers
must each be classified as controller, joint controller, or processor. Calling
everyone a "partner" does not resolve GDPR responsibility.

**Pseudonymisation is necessary but not always sufficient:**
Projects should use anonymised data where possible, otherwise pseudonymisation
plus access controls, SPEs, privacy-enhancing technologies, publication
controls, and restrictions on further use.

**Risk analysis is the starting point:**
High-risk medical, genetic, imaging, or AI research will frequently require
a DPIA and documented justification for the safeguards selected.

## Why it matters for this portfolio

This guidance directly affects every project in the portfolio that touches
personal or biomedical data (p1, p4, p10) and every infrastructure project
that stores or processes it (p9, homelab SPE framing).

The key consequence: vague claims like "this is research, therefore GDPR
allows it" are no longer defensible. Organisations must document:
- Why the activity is genuine scientific research
- The Article 6 and Article 9 legal basis
- Who controls each processing operation
- Why identifiable or pseudonymised data are necessary
- What happens when data are reused, shared, retained, or withdrawn
- Which technical, organisational, and ethical safeguards apply

For projects like BigPicture, EUCAIM, AIDA Data Hub, and medical imaging
repositories (the exact infrastructure context of this portfolio), metadata
about legal basis, permitted purpose, controller roles, access conditions,
retention, provenance, and safeguards becomes more important — not optional.

## Connections to existing projects

- **p5 — regulatory/compliance doc:** primary landing zone. The EDPB guidance
  provides the GDPR layer that sits alongside EU AI Act and EHDS/SPE. Together
  they form the full regulatory picture for biomedical research AI. The p5 doc
  should map each project to: legal basis, Article 9 condition, DPIA trigger,
  safeguards applied.
- **p9 — knowledge graph:** the guidance implies that metadata (legal basis,
  access conditions, controller roles, retention rules, provenance) needs to be
  machine-readable and queryable. p9's knowledge graph — especially the Phase 7
  institutional catalogue — is exactly the right layer for this. A SPARQL query
  like "which datasets have explicit consent as legal basis and allow reuse for
  oncology research" is the kind of query EHDS HealthData@EU and AIDA Data Hub
  need. This is a concrete extension to p9's scope.
- **SPE/EHDS topic (`spe-ehds.md`):** the guidance reinforces the SPE
  requirement — pseudonymisation plus access controls plus secure environments
  plus publication controls is the safeguard stack EDPB expects. The homelab
  SPE framing needs to reference this explicitly.
- **p1 — PCam deployment:** model trained on histopathology images (personal
  data). The guidance requires documented legal basis, DPIA, and safeguards
  even for training data used to build a classifier.
- **p4 — NLP on clinical abstracts:** reuse of existing publications as
  training data — likely falls under the reuse-without-compatibility-test
  provision, but still needs a documented legal basis.
- **p10 — BEETLE segmentation:** medical imaging of personal data. High-risk
  AI + Article 9 data → DPIA required. Grand Challenge's execution model
  (algorithm-to-data) satisfies the SPE requirement.

## Open questions

- [ ] Does the guidance change what p5's regulatory doc needs to say about
      p1 and p4 specifically? (They use public datasets — does the EDPB
      definition of "genuine scientific research" cover portfolio/learning
      projects?)
- [ ] Is p9's knowledge graph the right layer for GDPR metadata, or does
      this belong in a separate data catalogue (DCAT-AP, schema.org Dataset)?
- [ ] How does the consortium controller/processor classification apply to
      the homelab? (Who is the controller when the cluster processes BEETLE
      data — the researcher, the institution, or Grand Challenge?)
- [ ] The guidance is a consultation draft. What is the timeline to final
      adoption, and should the p5 doc be written against the draft or wait?

## Evidence / research

**2026-06-11** — User read and summarised the EDPB guidance. Key finding:
the guidance is research-friendly (reuse, broad consent, long retention
accepted) but accountability-heavy (legal basis, controller roles, DPIA,
safeguards must all be documented). It does not prohibit federated research
infrastructures — it provides a more defensible route provided governance is
explicit and enforceable.

**2026-06-11** — Connected to SPE/EHDS topic: the safeguard stack EDPB
expects (pseudonymisation + access controls + SPE + publication controls)
matches the TEHDAS2 SPE technical requirements. These two documents are
complementary — EHDS specifies the infrastructure, EDPB specifies the
governance.

## Decision

**Placed (partial):**
- p5 regulatory doc: add EDPB/GDPR research section. Map p1, p4, p10 to
  legal basis, Article 9 condition, DPIA trigger. Write alongside EHDS/SPE
  section — they form one coherent governance narrative.
- p9 Phase 7 extension: consider adding GDPR metadata layer (legal basis,
  access conditions, controller roles) as machine-readable triples. This
  would make p9's knowledge graph directly relevant to EHDS data catalogues
  and AIDA Data Hub-style infrastructure.
- Open questions above remain unresolved before full placement.
