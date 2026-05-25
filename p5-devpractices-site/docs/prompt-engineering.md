# Prompt Engineering
*p5 — Engineering Practices*

---

Prompt engineering is the discipline of defining constraints upfront —
before a build step executes, before a config is written, before a model
responds. The builder may be a human, an AI, or a CI job. The discipline
is the same: the quality of the output is bounded by the quality of the
constraints given to the producer.

This document records the constraints that apply in this portfolio,
with the reasoning behind each one. When working with AI tools, these
constraints are given as instructions before any task. When working
without AI, they are the checklist before the first line of config.

---

## Images and dependencies

**Always use the official image from the project's own organisation.
Check the official docs before writing any config.
Never pick a third-party image without explaining why the official one
was rejected first.**

An unofficial image may work. It may also be outdated, unmaintained,
or — in the worst case — malicious. The official image from the project's
own organisation is the only one with a clear chain of custody.

"I couldn't find the official one" is not a valid reason. That means
the official docs were not checked. Check them first.

If the official image has a genuine limitation that forces a third-party
choice, that reasoning is documented inline — in the Dockerfile, the
Helm values, or the commit message — not left implicit.

---

*This document is in development. Rules will be added as they are
identified across p1–p9.*
