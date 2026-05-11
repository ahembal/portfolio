# Tools
*p6-research-agent — LangChain tool machinery and our domain functions*

---

## langchain_core.tools — the external machinery

`langchain_core.tools` is a LangChain module that provides the infrastructure for
wrapping Python functions into objects the LLM agent can discover and call.

The key export is the `@tool` decorator:

```python
from langchain_core.tools import tool
```

### What @tool does

`@tool` takes a plain Python function and wraps it into a `StructuredTool` object.
A `StructuredTool` has three capabilities a plain function does not:

1. **Schema** — reads an `args_schema` (Pydantic model) and generates a JSON schema
   that is sent to the LLM. The LLM uses this to know what arguments the tool accepts.

2. **Validation** — when called via `.invoke(args_dict)`, it instantiates the Pydantic
   model, runs all validators, and only then calls the underlying function with clean values.

3. **Metadata** — name, description, and schema are all accessible as attributes on the
   tool object. LangGraph uses these to bind tools to the LLM and route calls.

### StructuredTool.invoke flow

```
tool.invoke({"query": "tp53", "organism": None})
        │
        ▼
args_schema(**args_dict)          ← Pydantic instantiation
  = UniprotInput(query="tp53", organism=None)
        │
        ▼
@field_validators run             ← validation and coercion
  query    = "TP53"  (uppercased)
  organism = "human" (None → default)
        │
        ▼
underlying function called        ← clean values only
  lookup(query="TP53", organism="human")
```

### args_schema vs invoke

These serve different purposes:

| | `args_schema` | `.invoke()` |
|---|---|---|
| When | At tool definition | At runtime |
| Purpose | Defines the input shape for LLM schema generation | Validates and calls the function |
| Used by | LangChain/LLM for schema | LangGraph `act` node |

`args_schema` is the blueprint. `.invoke()` is where the blueprint is applied.

---

## Our domain functions — internal tools

We have four domain functions that are wrapped with `@tool` to become agent-callable:

| Function | Module | External API |
|----------|--------|--------------|
| `pubmed_search` | `src/tools/pubmed.py` | NCBI Entrez |
| `pubmed_fetch` | `src/tools/pubmed.py` | NCBI Entrez |
| `uniprot_lookup` | `src/tools/uniprot.py` | UniProt REST |
| `rag_search` | `src/tools/vector_store.py` | ChromaDB (local) |

These are plain Python functions. By applying `@tool` with a Pydantic `args_schema`,
they gain the validation and schema capabilities described above.

---

## Why @field_validator with mode="before"

`mode="before"` means the validator runs before Pydantic checks the type:

```python
@field_validator("organism", mode="before")
@classmethod
def default_organism(cls, v):
    return v or "human"
```

Without `mode="before"`, Pydantic sees `None` for a `str` field and raises
`ValidationError` before our validator runs. `mode="before"` intercepts first.

---

## Why @classmethod on validators

Pydantic validators must be `@classmethod` because they run during model instantiation —
before any instance exists. `cls` receives the class itself. For single-field validators
that only use `v` (the incoming value), `cls` is not used in practice, but Pydantic
requires it by convention.

---

## The bug this fixed

**Symptom:** Query "what is tp53?" caused `uniprot_lookup` to fail with
`"No UniProt entry found for 'tp53' in <nil>"`.

**Cause:** Llama 3.1 8B passed `organism=None` when the user did not specify one.
Without validation, `None` reached the UniProt search as a literal value.

**Fix:** `@field_validator("organism", mode="before")` converts `None` → `"human"`.
`@field_validator("query", mode="before")` uppercases gene symbols since UniProt
gene search is case-sensitive (`"tp53"` → `"TP53"`).
