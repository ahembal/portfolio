# Observability
*Cross-cutting patterns for measuring and understanding service behaviour.*

---

## Percentile latency — p50, p95, p99

### Why not averages

Averages hide outliers. A service that responds in 10ms 99% of the time and
5000ms 1% of the time has an average of ~60ms — which looks acceptable but
means 1 in 100 users waits 5 seconds. The average is meaningless.

Percentiles tell the truth:

```
100 requests, sorted by latency:

  1ms  1ms  2ms  2ms  3ms ... 10ms 10ms 10ms ... 5000ms
  ──────────────────────────────────────────────────────
  p50 = 10ms   (50th request in sorted order)
  p95 = 50ms   (95th request)
  p99 = 5000ms (99th request)
```

- **p50** — median. Half of requests are faster, half are slower. Typical experience.
- **p95** — 95% of requests are faster than this. Near-worst-case experience.
- **p99** — only 1% of requests are slower. Worst-case that real users hit regularly.

### When to use each

| Percentile | Use for |
|------------|---------|
| p50 | Understanding typical behaviour |
| p95 | Setting SLOs for interactive services |
| p99 | Catching outliers, cold starts, memory pressure spikes |
| p99.9 | High-frequency systems where even rare spikes matter |

For a homelab portfolio serving occasional requests, p95 and p99 are the right
targets. p99.9 is for systems handling thousands of requests per second.

### In this portfolio

SLOs are defined in percentiles — see `p5-devpractices-site/slos/slos.yaml`:

| Service | Metric | Target |
|---------|--------|--------|
| p1 PCam inference | p99 latency | < 2000ms |
| p4 NLP inference | p95 latency | < 500ms |
| p6 Research agent | p95 latency | < 120s |

p1 uses p99 because CPU inference has occasional slow outliers (model cold start,
memory pressure). p4 uses p95 because lighter text inference should be reliably fast.

### In Prometheus

`Histogram` metrics record latency distributions. Grafana derives percentiles using
`histogram_quantile()`:

```promql
histogram_quantile(0.99, rate(pcam_request_latency_ms_bucket[5m]))
```

This query gives the p99 latency over the last 5 minutes — updated continuously.
Histogram buckets must be sized to match expected latency ranges. p1 uses buckets
`[5, 10, 25, 50, 100, 200, 500, 1000, 2000]` — tuned for CPU inference.

### In benchmarks

The p8 model registry benchmark runs each format (PyTorch, ONNX) N=100 times and
reports p50/p95/p99. This distinguishes:
- Consistent improvement (all percentiles improve) — worth switching
- Average improvement but high p99 (ONNX has occasional slow outliers) — investigate before switching
- No improvement — conversion adds complexity without gain

---

## Where percentile latency is used in industry

**Web services** — SLOs are always written in percentiles. "p99 < 200ms" is the
standard contract between a service and its callers.

**Databases** — PostgreSQL `pg_stat_statements` reports p99 query latency.
Slow query logs are triggered by p99 thresholds.

**CDNs** — Cloudflare, Akamai report p99 response times in customer dashboards
as part of their SLAs.

**Hardware** — NVMe SSD specs list p99.9 read/write latency. A drive with good
average but bad p99.9 fails real-time workloads.

**Finance** — high-frequency trading measures order execution in microsecond
percentiles. p99.9 matters when executing thousands of trades per second.

**Medicine** — ICU monitoring systems guarantee alarm latency within SLA windows
using p99 thresholds. Missing a threshold means a patient alert is delayed.

The pattern is universal: in any system where consistent performance matters —
not just average — percentiles are the standard measurement.

---

## Memory footprint

Memory footprint measures how much RAM a process uses. For ML serving this includes:

- **Model weights** — loaded once at startup, stay in RAM
- **Runtime overhead** — PyTorch keeps gradient state and Python objects; ONNX Runtime does not
- **Per-request peak** — temporary tensors during inference

Measured with `tracemalloc` (Python) or `psutil.Process().memory_info().rss`.

For serving containers, memory footprint determines:
- How many replicas fit on a node
- Whether the HPA can scale up under load
- Container resource limits in Helm values

---

## Output agreement

When benchmarking two implementations of the same model (e.g. PyTorch vs ONNX),
outputs must agree within a tolerance:

```python
assert abs(pytorch_prob - onnx_prob) < 1e-4
```

Floating point arithmetic differs between C++ (ONNX Runtime) and Python/PyTorch.
Bit-identical outputs are not expected — but the difference must be negligible.
A tolerance of `1e-4` (0.01%) is standard for classification probabilities.

If outputs diverge beyond tolerance, the ONNX export is broken and must not
be used in production regardless of performance.
