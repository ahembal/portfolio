# Implementation Notes — P5 Dev Practices Site
*Last updated: 2026-05-02*

This document describes how the project was built: structure chosen, decisions made during development, and the design change from MkDocs to Lovable. For how the finished site works see `how-it-works.md`.

---

## Design change: MkDocs → Lovable (2026-05-02)

Original plan was MkDocs + Material theme + GitHub Pages (static documentation site). Changed to Lovable (React) + Vercel hosting.

Reason: MkDocs produces a ReadTheDocs-style documentation look. A modern React site makes a stronger first impression for a portfolio. Lovable removes the need to write React from scratch while still producing a polished, branded result.

What stayed the same: all content (testing, CI/CD, security, observability, code quality) is unchanged. Evidence links point to the same repo files. The site is strictly dev practices — no personal bio.

## content.md

- Written first (content before build) — forces clarity on what each section actually claims
- 6 sections: testing strategy, CI/CD pipeline, security practices, observability, code quality, Q10 synthesis
- Each section includes evidence links pointing to actual files in p1–p4 repos
- No job application references in public files (kept out intentionally)

## lovable-prompt.md

- Full Lovable prompt: design spec (dark theme, amber accent, minimal), complete site structure, all section copy, technical requirements (React + Tailwind, dark/light toggle, mobile responsive)
- Written to be pasted directly into Lovable in one shot — no iteration needed if the prompt is complete
- Includes exact wording for each section to prevent placeholder text generation

## Pending

- Lovable build not yet done (step 18)
- Vercel deployment not yet done (step 19)
- Link from CV site not yet done (step 20)
