# Licensing

This portfolio uses a dual-license approach: one license for code, a different
one for documentation and educational content. The distinction matters because
the two types of work are used differently.

---

## Code — MIT License

All source code in this portfolio (Python, Helm charts, Dockerfiles, GitHub
Actions workflows, Kubernetes manifests) is released under the
**MIT License**.

MIT is the standard choice for portfolio and open-source code:
- Anyone can use, copy, modify, and distribute the code
- Commercial use is allowed
- The only requirement is that the original copyright notice is preserved
- No "share-alike" obligation — derivative projects can use any license

MIT is compatible with the Apache 2.0 and BSD licenses used by most of the
dependencies in this portfolio (PyTorch, HuggingFace Transformers, FastAPI,
RDFlib, etc.).

---

## Documentation and educational content — CC-BY 4.0

All documentation, guides, design documents, and educational content
(the `docs/` directories, `README.md` files, p5-devpractices-site content,
and the p0-incubator topic files) is released under
**Creative Commons Attribution 4.0 International (CC-BY 4.0)**.

CC-BY 4.0 means:
- Anyone can use, share, adapt, and republish the content
- Commercial and non-commercial use are both allowed
- The only requirement is attribution — credit the original author
- No share-alike obligation — derivative works can use any license

### Why CC-BY and not CC-BY-NC-SA

The previous version used CC-BY-NC-SA (Non-Commercial + Share-Alike).
CC-BY-NC-SA was changed to CC-BY 4.0 following ELIXIR Training Platform
guidance (Elin Kronander, 2026).

The NC restriction causes a practical problem in research infrastructure:
universities, hospitals, and organisations like ELIXIR and Euro-BioImaging
often cannot use NC-licensed material even for non-profit research activities,
because their legal definition of "commercial" is broad enough to exclude them.
CC-BY removes that ambiguity entirely — any organisation can reuse, translate,
or redistribute the content without legal review or asking for permission.

The SA restriction was dropped for the same reason: requiring derivative works
to use the same license limits adoption in institutional contexts where
licensing terms are set at the organisation level.

### Alignment with open science standards

CC-BY 4.0 is the license recommended by:
- ELIXIR Training Platform for training materials
- FAIR principles for research outputs (Findable, Accessible, Interoperable, Reusable)
- Euro-BioImaging for imaging facility documentation
- EHDS guidance for health data documentation and metadata

---

## What this means in practice

| Content type | License | Can you reuse it? |
|-------------|---------|-------------------|
| Python source code | MIT | Yes — copy, modify, use commercially |
| Helm charts, Dockerfiles, CI workflows | MIT | Yes |
| README files and project docs | CC-BY 4.0 | Yes — with attribution |
| Design documents and how-it-works guides | CC-BY 4.0 | Yes — with attribution |
| Training data and model weights | Upstream license | Check the upstream dataset/model card |

Training data and model weights are not covered by this portfolio's license —
they are subject to the licenses of the original datasets (PCam, PubMed RCT,
BEETLE). See each project's `docs/security.md` or `SPEC.md` for the upstream
license terms.

---

## Attribution

When reusing documentation from this portfolio, attribution should read:

> Based on material from the ML Engineering Portfolio by Emre Balsever,
> licensed under CC-BY 4.0.
