# Conventional Commits

Standard for writing structured, machine-readable commit messages.
Spec: conventionalcommits.org

---

## Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

---

## Subject line rules

- Imperative tense: "add feature" not "added feature"
- No capital first letter
- No period at the end
- Under 72 characters
- `scope` is optional — use the project or module name (e.g. `p6`, `infra`, `p7`)

---

## Types

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or fixing tests |
| `ci` | CI/CD pipeline changes |
| `chore` | Maintenance — dependency updates, config, tooling |

---

## Body — WHY, not WHAT

The body explains the motivation for the change. The diff already shows what
changed — the body answers why it was necessary.

**Good:**
```
fix(p6): synthesise answer when LLM returns empty content

Llama 3.1 8B in tool-use mode emits empty message content after tool
calls. Without a fallback, the API returns an empty answer to the caller.
```

**Bad:**
```
fix(p6): added synthesis fallback block in main.py after line 76,
changed answer variable assignment, added HumanMessage import
```

---

## Footer

Used for co-authors, issue references, and breaking change notices:

```
Assisted by Claude
Closes #42
BREAKING CHANGE: query endpoint now requires `version` header
```

---

## Examples from this repo

```
feat(p7): implement hybrid retrieval pipeline
fix(p1): use full SHA in values.yaml
docs(infra): document storage architecture and strip Tailscale IPs
ci(p6): update image tag to 5303154
chore: add hosts.local.md to gitignore
```
