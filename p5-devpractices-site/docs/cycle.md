# The Development Cycle
*p5 — Engineering Practices*

---

A project does not begin with a model, a schema, or a sprint plan.
It begins with thinking — about what the problem actually is, about what we
believe good engineering looks like, and about why those beliefs exist.

This document describes the full cycle as practiced in this portfolio,
from that foundational thinking through to running production software.

---

## Stage 0 — Before the model, before the schema

Before the model, before the schema — the why and the how we think,
not the what we build.

Like a constitution before the laws.

Every project in this portfolio is preceded by four things, sometimes written
explicitly, sometimes held implicitly. Making them explicit is the point of
this stage.

### Principles
What we consistently do — and consistently refuse to do.
Named beliefs that survive the pressure of a deadline.
Examples: tests as a spec made executable, not a formality.
Security decisions that reference standards, not instinct.
Observability designed before deployment, not added when something breaks.

### Philosophy
How we reason about a problem, not just what we conclude.
The mental model behind the decisions. The frame that makes specific choices
feel inevitable rather than arbitrary.
Example: a mocked database test is not a test of the system — it is a test of
the mock. That reasoning drives the testcontainers choice in p2.

### Manifesto
The positions we hold and are willing to defend.
Stronger than a principle — a manifesto expects disagreement and states the
case anyway.
Example: the medium reinforces the message. A dev practices site that has no
build pipeline, no Docker image, and no automated deployment would contradict
its own content. So it has all three.

### Charter
The formal commitments — what this project will do, and what it is explicitly
out of scope.
A charter is a contract with yourself. It prevents scope creep not by
willpower but by having written down, before you started, what this project
is not.
Example: p9 SPEC.md — "GraphRAG: planned as next step. Out of scope for this
project."

These four are not separate documents in every project. They can be a section
of a SPEC, a paragraph in a README, or a paragraph in your head. What matters
is that they are resolved before the schema is drawn.

---

## Stage 1 — Problem definition

SPEC.md: what and why, what to build, what is out of scope.

The SPEC is not a requirements document. It is an argument — for why this
problem is worth solving, why this approach over alternatives, and why these
boundaries and not wider ones.

A SPEC that cannot be argued from is a SPEC that will drift.

---

## Stage 2 — Data and schema design

Before any code: what are the entities, what are their relationships,
what are the constraints.

A schema is a theory about the domain. Getting it wrong early is cheap.
Getting it wrong in production is not.

---

## Stage 3 — Implementation

Build what the SPEC specifies. No more, no less.

Three similar lines is better than a premature abstraction.
A one-shot operation does not need a helper function.
Don't design for hypothetical future requirements.

---

## Stage 4 — Testing

The right test type for the right failure mode.

Unit tests validate logic in isolation.
Integration tests validate real dependencies — not mocks of them.
Load tests validate that the system behaves under realistic throughput.

The choice of test type is a design decision.

---

## Stage 5 — CI/CD

lint → test → build → push → values.yaml update → ArgoCD deploys.

The pipeline is the same across p1, p2, p4. Not by accident — by decision.
Consistency in the pipeline means a reviewer can predict what will happen
in a project they have not read yet.

---

## Stage 6 — Observability

Metrics designed before deployment.

Not added reactively when something breaks.
The choice of metric type (Counter vs Gauge vs Histogram) is a reasoning
decision, documented alongside the metric definition.

---

## Stage 7 — Documentation

Evidence-backed, not claims.

Every assertion in a doc links to the file, commit, or config that proves it.
A doc without evidence is a belief, not a record.
Timestamps are visible so staleness is visible.

---

## Stage 8 — Review and iteration

PROGRESS.md tracks what is done, what is next, and why the current state
is the current state.

Iteration is not a failure of planning. It is how understanding deepens.
The SPEC does not change because the plan was wrong — it changes because
the project taught us something the plan could not have known.

---

*This document is in development. Stages will be expanded with evidence links
and worked examples from p1–p9.*
