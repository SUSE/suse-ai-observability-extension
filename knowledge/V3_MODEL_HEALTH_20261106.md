# Direct model health and serving direction — 2026-11-06

The demo is installed at **3.0.0-dev.94**, instance `261989587621111`.
Both dev.93 and dev.94 were uploaded once and upgraded with
`--unlocked-strategy overwrite`. The release source remains 3.0.0.

## Before and after

| Area | Previous demo, dev.92 | Current demo, dev.94 |
| --- | --- | --- |
| Serving relation | Model → engine, `is-hosted-on` | **Engine → model, `serves-model`** |
| Topology layout | Models above their engines | Models below their engines |
| Ollama model health | Inherited hosting-service health | **Direct model inventory/API availability check** |
| Available but unloaded Ollama model | Inherited health | Healthy when present in a fresh successful inventory; loaded state 0 is valid |
| Observed API failure or missing model | Reflected only through engine health | DEVIATING when no observed replica supplies fresh evidence for this model |
| Missing Ollama telemetry | Could retain a hosting-service assertion | New monitor emits no check; observations older than two minutes are excluded |
| vLLM model health | Existing end-to-end and time-to-first-token checks | Same direct latency checks and monitor IDs |
| Agent health | Hosting-service inheritance | Same behavior; derived monitor now targets agents only |
| Model identities and links | Four served-model components | Same four numeric IDs/URNs; Served by and Hosting inference service still link to their engines |
| Models table | Six columns, four rows | Same columns and rows, with direct model health |
| AI overview | Five columns, 21 rows | Same table; topology has 21 individual components and no collapsed group in this capture |
| GPU nodes | Four rows, 17 columns | Same rows and table metadata |
| Native Open Telemetry pages | Native Services and Service instances | Same table metadata; current screenshots included below |
| Navigation | Six grouped submenus | Same six: Overview, Applications & agents, Models, Inference, Data services, GPUs |
| Monitors | 68 installed monitors | All 68 IDs preserved, plus `ollama-model-unavailable` (69 total) |
| Menu and component icons | Supplied SUSE chameleon and compact icons | No icon changes |

The previous GPU-field comparison and earlier menu/component redesign are in
[GPU recovery and topology](V3_GPU_AND_TOPOLOGY_REVIEW_20261106.md),
[grouped views](V3_GROUPING_COMPARISON_20261106.md) and
[health columns](V3_HEALTH_TABLES_20261106.md).

## What the Ollama check measures

`ollama_model_loaded` exists for available models whether loaded (1) or unloaded
(0). Ollama's [loaded-model endpoint](https://docs.ollama.com/api/ps) and
[available-model endpoint](https://docs.ollama.com/api/tags) describe distinct
sets. Treating loaded state 0 as a failure would flag normal on-demand behavior.

The monitor matches cluster, namespace, service and model. Availability requires
the model observation and the latest successful `ollama_api_up` observation to
have the same timestamp on an observed replica. Any such replica can serve the
model. An older successful scraper cannot mask a newer failed observation on the
same replica. Cluster matching uses a literal escaped pattern, including an exact
empty match when the cluster attribute is absent.

A fresh API failure, or a fresh inventory without this model on every observed
replica, produces availability 0 and DEVIATING. With no fresh API observation the
query returns no sample and the monitor emits no check. This is not a dedicated
telemetry-loss alert, and a previous check may remain visible in history. An
intentionally removed model remains in topology until its 15-minute discovery
retention expires. The check establishes inventory/API availability, not successful
inference, response quality or latency. vLLM's existing latency checks retain
their own traffic-dependent coverage.

The live final run returned CLEAR for `gemma:2b`, `llama3.2:latest` and
`nomic-embed-text:latest`. `gemma:2b` was unloaded. Both vLLM checks returned CLEAR
for `qwen-small`; the derived-health run returned only `demo-agent`.
The model's one-hour monitor timeline still shows the earlier derived check as
history; its line ends before the current direct check. It does not indicate
that model inheritance is still running.

## Upgrade observations and validation

The new serving relations appeared before the old hosting relations expired.
Final topology contains exactly four engine-to-model serving links, no reverse
model hosting links, and the unchanged agent-to-service hosting link.

The installed dev.94 mapping initially had its new cluster-binding tag while live
components still had the old output. The demo topology connector has a one-hour
deduplication cache and refresh fraction 0.5. Restarting only
`suse-observability-otel-collector-0` produced the new tags and healthy direct
checks. The replacement became Ready and its StatefulSet specification compared
equal to the saved specification. This is an observed refresh workaround, not
proof of a specific cache implementation defect or a claim that every upgrade
requires a restart. Product workloads were not restarted.

- Native suite: **109 tests**, 18 opt-in checks skipped, no failures.
- Release/deployment suite: **24 passed**.
- Native validator: **118 nodes accepted**, invalid-CEL control rejected.
- All 31 threshold monitor queries have failing/recovering/no-data fixtures.
  The new Ollama query also passes 12 scenarios covering transitions, missing or
  stale data, replicas, clusterless observations and identity isolation.
- Native previews passed all nine states for the Ollama availability and two
  vLLM latency monitors. No synthetic telemetry or test health state was persisted.
- All **175** staged package files match the source except the dev manifest version.
- Both topology synchronizations are Running. Agent reports 10 errors and
  Kubernetes 33, as in this iteration's baseline. Existing details concern
  unresolved process/API targets and duplicate Kubernetes relations; they were
  not cleared. All 19 observed SUSE AI mappings have no mapping errors. Two
  unobserved database mappings return 404, as before.

This change addresses model layout and health. The earlier UX review's limits
around sparse model-usage components and GPU device-bound health remain recorded
in [the adversarial review](V3_UX_REVIEW_20261106.md).

## Where to look

Open **SUSE AI → Overview → Topology** for the engine-to-model layout. Open
**SUSE AI → Models → gemma:2b** for an unloaded but healthy model, its loaded-state
chart, direct monitor and serving-engine links. `llama3.2:latest` and
`nomic-embed-text:latest` exercise the same availability check. `qwen-small` keeps
the two direct vLLM latency checks.

- AI topology: [before](/home/thbertoldi/suse/qa/demo-model-health-ask5vpnl/topology-before/suse-ai.png)
  / [after](/home/thbertoldi/suse/qa/demo-model-health-ask5vpnl/ui-refreshed/suse-ai.png).
- Open Telemetry topology: [before](/home/thbertoldi/suse/qa/demo-model-health-ask5vpnl/topology-before/opentelemetry.png)
  / [after](/home/thbertoldi/suse/qa/demo-model-health-ask5vpnl/ui-refreshed/opentelemetry.png).
- [Models table](/home/thbertoldi/suse/qa/demo-model-health-ask5vpnl/ui-refreshed/models.png)
  and [gemma highlights with loaded state 0](/home/thbertoldi/suse/qa/demo-model-health-ask5vpnl/model-detail/gemma-loaded.png).
- [Direct Ollama model check](/home/thbertoldi/suse/qa/demo-model-health-ask5vpnl/model-detail/gemma-check.png).

Evidence root: `/home/thbertoldi/suse/qa/demo-model-health-ask5vpnl/`.
`inspection-final/` contains topology-sync list/descriptions and mapping statuses;
`final/` contains identity/table comparisons and live health runs;
`monitor-previews-final/` contains preview inputs/results. Browser captures are
actual demo responses; no responses or screenshots were mocked. Raw credentials,
backend configuration backups and captures remain outside Git. No SA operation,
registry push or older-state restoration occurred.
