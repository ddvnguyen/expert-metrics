# expert-metrics

Recorded expert-routing analysis for MoE LLMs — the data lake behind the
Hydra **expert-atlas** ([hydra_vortex#771](https://github.com/ddvnguyen/hydra_vortex/issues/771)).

Three metric families are recorded per model, per run:

| Family | Source | Metrics |
|---|---|---|
| **Colibri probe metrics** | [JustVugg/colibri](https://github.com/JustVugg/colibri) probe methodology (10 categories × 3 prompts, confound-controlled greedy) | affinity p(c\|e), mean share, specialization **spec = 1 − H/log C**, entropy, top, labels |
| **REAP saliency** | [CerebrasResearch/reap](https://github.com/CerebrasResearch/reap) (ICLR 2026) | router-weighted expert activation pruning score (gate value × activation norm, renormalized router weights), layer-wise utilization, routing collapse |
| **Edge0 predictability** | [Edge0-AI/Edge0](https://github.com/Edge0-AI/Edge0) | prerouter routing-prediction hit-rate — how predictable expert selection is before the router fires (expert-offload prefetch relevance) |

## Layout

```
schema/                     JSON schemas (run-record, experts, manifest)
tools/                      collector + validator (CI-gated)
models/<model_hash>/        one directory per recorded model
  manifest.json             provenance: engine_id, geometry, env gates, commits
  runs/<run_id>/            raw per-probe records (incl. honest telemetry:false)
  artifacts/                derived: experts.json, reap.json, edge0.json, experts.pin
```

## Honest-state discipline

Runs recorded while engine telemetry is absent (`telemetry_enabled: false`)
are **recorded as-is** — an explicit OFF record, never zeros pretending to be
data. Derived artifacts are only emitted when telemetry was present and the
replication gate passed (Colibri ≥2 probes/category, ≥2 categories).
Statistical gates are null-tested with random-routing controls before use.

## Consumers

- **atlas-web / Brain** (hydra_vortex): renders the Metrics tab from
  `artifacts/experts.json` (Colibri + REAP + Edge0 fields, one artifact).
- **llama.cpp fork** `tools/expert-atlas/`: probe harness + analyzer producing
  the records (pin-file exporter for the CPU-side expert cache).

## Provenance invariants

Every record and artifact carries: `engine_id` (FNV-1a64 of model path),
`model_hash` (GGUF file name), `llama_cpp_commit`, `atlas_stage` (B/C1/C2/A),
and the confound-control block (temperature/top_p/top_k/min_p, decode-only,
MTP-off). Engine-id refusal applies: artifacts from one engine are never
consumed by another model's views.
