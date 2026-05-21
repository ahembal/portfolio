#!/usr/bin/env bash
# Rebuild graph.ttl, reload Fuseki, run RAG vs SPARQL comparison.
#
# Usage:
#   export FUSEKI_NODE=<node-ip>          # e.g. 100.x.x.x
#   export FUSEKI_PASSWORD=admin          # default from values.yaml
#   export OLLAMA_BASE_URL=http://<ip>:<port>   # only needed for full RAG run
#   bash scripts/rebuild_and_compare.sh
#
#   # SPARQL-only (no Ollama needed):
#   SPARQL_ONLY=1 bash scripts/rebuild_and_compare.sh

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────

FUSEKI_NODE="${FUSEKI_NODE:?Set FUSEKI_NODE to the cluster node IP}"
FUSEKI_PORT="${FUSEKI_PORT:-30900}"
FUSEKI_PASSWORD="${FUSEKI_PASSWORD:-admin}"
SPARQL_ONLY="${SPARQL_ONLY:-0}"

FUSEKI_BASE="http://${FUSEKI_NODE}:${FUSEKI_PORT}"
GRAPH_TTL="data/seed/graph.ttl"

# ── Step 1: rebuild graph.ttl ─────────────────────────────────────────────────

echo ""
echo "=== Step 1: rebuilding graph.ttl ==="
echo "  10 seed proteins × up to 50 papers each — takes 5–10 min"
echo ""

python src/builder.py

echo ""
echo "  graph.ttl written: $(du -sh $GRAPH_TTL | cut -f1)"

# ── Step 2: reload Fuseki ─────────────────────────────────────────────────────

echo ""
echo "=== Step 2: reloading Fuseki ==="
echo "  endpoint: ${FUSEKI_BASE}/p9"
echo ""

# Verify Fuseki is reachable
if ! curl -sf --max-time 5 "${FUSEKI_BASE}/\$/ping" > /dev/null; then
    echo "ERROR: Fuseki not reachable at ${FUSEKI_BASE}"
    echo "  Check FUSEKI_NODE and that the pod is running."
    exit 1
fi

# Replace the default graph entirely (PUT = replace, not append)
echo "  uploading graph.ttl..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    "${FUSEKI_BASE}/p9/data" \
    -H "Content-Type: text/turtle" \
    --data-binary "@${GRAPH_TTL}" \
    -u "admin:${FUSEKI_PASSWORD}")

if [[ "$HTTP_STATUS" != "200" && "$HTTP_STATUS" != "201" && "$HTTP_STATUS" != "204" ]]; then
    echo "ERROR: Fuseki upload failed (HTTP ${HTTP_STATUS})"
    echo "  Check FUSEKI_PASSWORD and that the /p9/data endpoint is enabled."
    exit 1
fi

# Verify triple count
TRIPLE_COUNT=$(curl -sf \
    "${FUSEKI_BASE}/p9/sparql" \
    --data-urlencode "query=SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }" \
    -H "Accept: application/sparql-results+json" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['results']['bindings'][0]['n']['value'])")

echo "  Fuseki loaded: ${TRIPLE_COUNT} triples"

if [[ "$TRIPLE_COUNT" -lt 10000 ]]; then
    echo "WARNING: triple count looks low (expected 100k+). Check builder logs."
fi

# Quick smoke test: papers mentioning TP53
TP53_COUNT=$(curl -sf \
    "${FUSEKI_BASE}/p9/sparql" \
    --data-urlencode "query=PREFIX p9: <http://portfolio/p9/>
PREFIX uprot: <http://purl.uniprot.org/uniprot/>
SELECT (COUNT(?p) AS ?n) WHERE { ?p p9:mentions uprot:P04637 }" \
    -H "Accept: application/sparql-results+json" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['results']['bindings'][0]['n']['value'])")

echo "  Smoke test — papers mentioning TP53: ${TP53_COUNT}"

if [[ "$TP53_COUNT" -eq 0 ]]; then
    echo "ERROR: no TP53 papers found. p9:mentions edges are missing."
    echo "  The graph may have loaded but the builder output is wrong."
    exit 1
fi

echo "  Fuseki reload: OK"

# ── Step 3: run comparison ────────────────────────────────────────────────────

echo ""
echo "=== Step 3: running comparison ==="

export P9_SPARQL_ENDPOINT="${FUSEKI_BASE}/p9/sparql"

if [[ "$SPARQL_ONLY" == "1" ]]; then
    echo "  mode: SPARQL-only (set SPARQL_ONLY=0 and OLLAMA_BASE_URL for full run)"
    python scripts/run_comparison.py --sparql-only
else
    echo "  mode: full (SPARQL + RAG via Ollama)"
    echo "  Ollama: ${OLLAMA_BASE_URL:-http://ollama:11434}"
    python scripts/run_comparison.py
fi

echo ""
echo "=== Done ==="
echo "  Results in results/"
echo "  Copy the .md table into docs/comparison.md"
