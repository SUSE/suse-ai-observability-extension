# Customer-facing monitor names — 2026-11-06

The demo is installed at **3.0.0-dev.96**, instance `261989587621111`.
Versions dev.95 and dev.96 were uploaded once each and upgraded with
`--unlocked-strategy overwrite`. The release source remains 3.0.0.

## What changed

All **32 SUSE AI monitor names and descriptions** now explain what is being
monitored and why it matters. The **31 threshold check titles and chart labels**
use the same vocabulary and retain their actual service, model or node context.
Names describe availability, reliability, response time, resource use or monitoring
coverage. Health state communicates whether attention is needed, so a healthy
model no longer appears under a check title asserting that it is unavailable.

Examples rendered against real demo components:

- `Endpoint availability: ollama`
- `Model availability: gemma:2b on ollama`
- `Time to first token: qwen-small on vllm-qwen-small-engine-service`

Descriptions connect the measurement to a practical consequence while preserving
its scope. A metrics scrape failure means lost monitoring coverage; it does not
establish an API outage. Qdrant's memory check uses an absolute threshold, not a
fraction of node capacity. An NVIDIA XID code is labelled a GPU error without
assuming a hardware root cause. Ollama inventory availability still does not
claim successful inference or response quality.

Queries, thresholds, severity, intervals, bindings, identifiers and remediation
hints are unchanged. Existing D6 Check first / Likely causes / Fix / Verify guidance
continues to explain the response to a failing check. The shared platform-derived
agent check still uses its built-in `Derived health state` check title; the owned
catalog entry is now **AI agent dependency health**. No replacement monitor
function was added merely to rename that shared output.

## Complete catalog comparison

| Previous name | New name |
| --- | --- |
| AI agent: hosting service health | AI agent dependency health |
| Service service: endpoint probe fails | AI endpoint availability |
| AI application service: metric stream stopped | AI telemetry freshness |
| KServe controller service: reconciliation is stuck | KServe controller processing time |
| KServe controller service: reconciliation is failing | KServe deployment update errors |
| KServe service: predictions are slow | KServe prediction response time |
| Milvus service: requests are failing | Milvus request reliability |
| Milvus service: requests are slow | Milvus request response time |
| Milvus service: vector searches are slow | Milvus vector search response time |
| Model registry service: API probe fails | Model Registry API availability |
| Model registry service: API probe is slow | Model Registry response time |
| Model registry service: API response is invalid | Model Registry response validation |
| Model called by service: requests are failing | Model request reliability |
| Model called by service: calls are slow | Model response time |
| GPU node: NVIDIA XID errors are reported | NVIDIA GPU errors |
| Ollama model: unavailable in runtime inventory | Ollama model availability |
| OpenSearch service: primary shards are unavailable | OpenSearch data availability |
| OpenSearch service: replicas are unassigned | OpenSearch replica availability |
| Pipelines API service: metrics endpoint is unreachable | Pipeline API metrics availability |
| Pipelines service: gRPC errors are elevated | Pipeline API request reliability |
| Workflow controller service: images cannot be pulled | Pipeline container image availability |
| Workflow controller service: workflows are failing | Pipeline workflow failures |
| Qdrant service: active memory is high | Qdrant active memory usage |
| Qdrant service: gRPC requests are failing | Qdrant gRPC request reliability |
| Qdrant service: HTTP requests are failing | Qdrant HTTP request reliability |
| Qdrant service: HTTP responses are slow | Qdrant HTTP response time |
| Inference server service: KV cache is nearly full | vLLM GPU cache usage |
| Model on service: requests are slow | vLLM model response time |
| Inference server service: requests are queueing | vLLM request backlog |
| Model on service: first token is slow | vLLM time to first token |
| Workflow controller service: metrics endpoint is unreachable | Workflow controller metrics availability |
| Workflow controller service: queue processing is delayed | Workflow controller processing time |

## Verification

- All **69 installed monitor numeric IDs and identifiers are preserved**. All 32
  owned names/descriptions and 31 title/chart-label definitions match the installed
  settings. Names of monitors supplied by other StackPacks are unchanged.
- A parsed before/after comparison verifies that only display names, descriptions,
  check-title templates and chart aliases changed. Every title retains exactly its
  previous set of runtime substitutions. All **175** staged package files match
  source apart from the development manifest version.
- Native suite: **109 tests**, 18 opt-in checks skipped, no failures.
  Release/deployment suite: **24 passed**. The native validator accepted **118
  nodes** and rejected its invalid-CEL control.
- All 31 threshold monitors passed **93 native previews** covering failing,
  recovering and no-data states on dev.95. The final GPU wording refinement passed
  three additional previews on dev.96. No synthetic telemetry or test health states
  were persisted.
- Original-query dry runs verified **45 populated check titles** against actual
  metric labels with no unresolved substitutions. Fifteen monitors had no current
  check in that live dataset; their configured text and preview behavior were
  verified, without inventing product telemetry. The derived run still targets
  only the agent.
- Both topology synchronizations are Running. Agent reports **10 errors / 10
  active details**, and Kubernetes **33 / 10**, matching this iteration's baseline
  counts. Existing unresolved targets and duplicate relations were not cleared.
  All **19 observed SUSE AI mappings** have no mapping errors; two unobserved
  database mappings still return 404.

This is a wording change. Menus, overview-table columns, component identities,
serving relations, product coverage and monitor evaluation behavior are unchanged.
The model-health/layout comparison remains in
[Direct model health and serving direction](V3_MODEL_HEALTH_20261106.md).

## Where to look

Open **Main menu → Monitors** for the new catalog names. Open
**SUSE AI → Models → gemma:2b → Monitors** and select
**Model availability: gemma:2b on ollama** for the customer-facing check title,
description and evidence. The model can remain CLEAR while its loaded-state chart
shows 0.

- Catalog [before](/home/thbertoldi/suse/qa/demo-monitor-names-bbl9xy2a/ui-before/monitors.png)
  / [after](/home/thbertoldi/suse/qa/demo-monitor-names-bbl9xy2a/ui-final-router/monitors.png).
- [Model-related catalog names](/home/thbertoldi/suse/qa/demo-monitor-names-bbl9xy2a/ui-final-router/model-monitors.png).
- [Model check and description](/home/thbertoldi/suse/qa/demo-monitor-names-bbl9xy2a/model-after-connected/gemma-check.png).

Private evidence: `/home/thbertoldi/suse/qa/demo-monitor-names-bbl9xy2a/`.
`audit-final.json` records the installed text, preserved IDs, mapping statuses and
live title verification. `previews/` and `gpu-preview-final/` contain the preview
inputs/results. Deployment verification snapshots are under
`/home/thbertoldi/suse/qa/demo-v3-deploy-state-20261106/versions/3.0.0-dev.96/verification/`.
The browser used actual demo responses. The final catalog capture used the local
router tunnel; its WebSocket live updates returned 403, so catalog text was also
verified against the HTTP API. The authenticated HTTPS model-check screenshot is
from dev.95; its text is identical in dev.96, which only refines the GPU label.
Credentials, raw snapshots and screenshots remain outside Git. No SA operation or older-state restoration occurred.
