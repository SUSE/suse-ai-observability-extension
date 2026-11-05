# Ollama served-model inventory (release 3.0.0)

The release target was changed to 3.0.0 after validation. Historical 3.0.1
uploads, image references and evidence below describe the builds actually tested.

## Design decisions, before implementation

The component source is `ollama_model_info{model,family,parameter_size,quantization}`
with value 1, from the read-only [`GET /api/tags`](https://docs.ollama.com/api/tags).
[`GET /api/ps`](https://docs.ollama.com/api/ps) describes loaded models only.
Unloading after `keep_alive` must not remove an available model from topology.
Each scrape reads both endpoints without caching. If either read or validation
fails, emit only `ollama_api_up 0`; never reuse an earlier inventory or residency
snapshot. An empty valid inventory is a successful observation.

Preserve existing `/api/ps` allocation metrics and their meaning. Add
`ollama_model_loaded{model}` (0 or 1 for each available model) and
`ollama_model_disk_size_bytes{model}` from `/api/tags`; disk size and loaded
allocation are different quantities. An unloaded model reports zero loaded
state and zero VRAM; context length and loaded allocation remain unreported.
Missing optional fields on a loaded model remain unreported. Metadata labels
are descriptive and do not participate in identity.

The Ollama identifier uses the existing served-model structure:
`urn:suse-ai:[cluster/<cluster>:]namespace/<ns>:service/<svc>:served-model/<model>`.
Cluster is included only when nonempty. Pod UID and metadata changes do not
change this logical identity. Keep vLLM identifiers unchanged for compatibility.
The serving relation and inventory link target the existing native service
identifier `urn:opentelemetry:namespace/<ns>:service/<svc>`. Native service IDs
omit cluster, so deployments with identical service namespace/name across
clusters still need distinct logical namespaces to disambiguate that link.

Values remain unescaped, matching the documented convention in
`examples/suse-ai/README.md`: ordinary colons (`gemma:2b`, `llama3.2:latest`) and
slashes are valid; embedded field separators such as `:service/` can collide.
Do not silently URL-encode model names or rewrite `:latest`. Prometheus label
escaping is a separate requirement from topology identifier construction.

Use `expireAfter: 900000` (15 minutes), matching vLLM, for both the model and
its serving relation. Every successful inventory scrape refreshes these even
when `/api/ps` is empty. Deletion or prolonged API failure stops updates and
allows expiry; expiry is backend processing time after the last observation,
not an immediate deletion guarantee. A model available on any observed replica
continues to refresh the logical service/model component.

The Models page and general served-model presentation share product-neutral
identity columns: name, hosting service link, namespace, product and cluster.
Keep vLLM charts and add an Ollama served-model presentation for loaded state,
VRAM, available disk size, loaded allocation and context. Unsupported metric
columns must explicitly say `not reported`; no numeric zero may stand in for
unknown data. The pinned backend's `MetricProjection` has only query, unit,
decimalPlaces, sparkline and metricId fields, without a missing-value text or
conditional projection. Therefore the shared table uses text columns for metric
availability, with `See model charts` for supported metrics and `not reported`
otherwise. The three existing numeric vLLM columns move to its product-specific
overview; all vLLM charts retain their queries. Charts select the exact model and service, scope Ollama by cluster,
deduplicate scrapers per pod UID, and gate values on the latest successful API
observation so old Prometheus samples cannot survive a failed read.

Request-side metrics belong to callers. Model name plus `server.address`/port
is insufficient evidence of the serving service: endpoints can be proxies,
aliases or remote hosts, and `llama3.2` need not equal `llama3.2:latest` without
runtime verification. Evaluate the actual demo metric labels and explicit peer
identity contract before adding attribution. Where peer identity is absent or
unverified, keep requests/latency/tokens on caller model-usage components; do not
join by model name alone or assign all caller traffic to Ollama. The November 5
demo's duration counters have no explicit peer-service labels; several callers
also omit `server_address`/`server_port`, and some use untagged model aliases.
No request-side served-model attribution is added in 3.0.0. A future integration
must attach verified peer service namespace/name/cluster to each measurement
and verify any model alias before a scoped aggregation can be implemented.

## Validation and demo scope

Extend executable CEL mapping contracts, real Prometheus query fixtures and
presentation identity checks, retaining the vLLM suite. Exercise loaded to idle
transitions through the exporter and actual mapping expressions, continued
refresh beyond 15 minutes, deletion, endpoint failures and replica/cluster
separation. Validate native settings before the single 3.0.1 upload.

Build and test the exporter locally as 3.0.1. Save the live exporter image and
workload specs before testing; restore the exporter afterward. Do not change
demo applications, model availability, Collector configuration or backend
workloads. Upgrade the StackPack with `--unlocked-strategy overwrite`, record
API/UI evidence and compare mapping and topology-sync errors to the baseline.
The first baseline already contains active Agent/Kubernetes sync errors; their
presence is not evidence of an Ollama mapping regression.

## Monitoring guide handoff

Update the guide's Ollama setup/image version, read-only API requirements,
metric table, available-versus-loaded model explanation, Models page/service
link workflow, replica aggregation, 15-minute deletion/failure expiry,
unreported context/allocation semantics, and request attribution limits.
The exporter and StackPack must both be upgraded for available-model discovery.
Restoring the old exporter after a demo test stops inventory refresh; models
will expire again even while old residency charts continue working.

Concrete downstream guide edits (in `~/suse/doc-suse-ai`, not modified here):

| Topic | Required update |
| --- | --- |
| `articles/ai-monitoring.adoc` | Set StackPack/exporter attributes to 3.0.0 when released; align the extension tag |
| `tasks/AI-monitoring-ollama-runtime.adoc` | Describe both read-only endpoints, add inventory/loaded/disk-size gauges, compare `/api/tags` as well as `/api/ps`, and add Models-page/service-link verification |
| `references/AI-monitoring-integrations.adoc` | Describe available-model topology and version requirement in the Ollama runtime row |
| `tasks/AI-monitoring-native-owui.adoc` | Explain caller-side request metrics and the need for verified peer/model attribution before attaching them to a served model |

## Validation record (2026-11-05)

Work is on `feat/ollama-model-inventory-3.0.1`. The demo catalog contained 2.0.0
and 3.0.0 before this test. `task stackpack-upload` validated and packaged 3.0.1,
uploaded it once, and ran the existing installer. Instance `197048877569388`
upgraded from 3.0.0 to 3.0.1 with `--unlocked-strategy overwrite`, retaining its
ID and reaching `INSTALLED`. No changed payload was uploaded under the same
version. All 155 archived files match their current source bytes.

Archive SHA-256:
`40e10e4478d52ecae08b06344540a75f92729472fa94c1f1f13c2cc6a33bace8`.

| Check | Result |
| --- | --- |
| Full native suite, including existing vLLM and real Prometheus cases | 73 passed; 12 opt-in backend tests skipped |
| Added backend presentation test | Imports successfully; opt-in fixture test skipped, with actual demo checks performed separately below |
| Release/package/installer suite | 15 passed |
| Exporter HTTP suite | 11 passed |
| Strategic-merge patch suite | 2 passed |
| Locally built amd64 image | 2 container tests passed: endpoints, loaded/idle/failure snapshots, UID/GID 65532, read-only filesystem, zero capabilities, no-new-privileges and seccomp |
| Pinned native validator | 96 settings accepted; undeclared-CEL negative control rejected |

The idle contract fixture feeds actual exporter output into the shipped CEL
every 30 seconds for 30 simulated minutes, including idle time beyond the
15-minute expiry interval. Identity and relation target stay stable, and deletion
stops emitting inventory. Prometheus fixtures check absent data, unload, deletion,
failed API reads, stale samples, duplicate scrapers, and model/service/cluster
separation. This is not a live model-deletion or backend expiry timing test.
The demo's vLLM runtime was not exercised; its existing mapping/relation files
and chart queries are unchanged, and its regression tests pass.

The locally built `local.invalid/suse-ai-ollama-exporter:3.0.1` image (image ID
`sha256:c41834445bb5e808638e49774693e1ae1774d4edaf0f5bcb69b8868394d00969`)
was imported directly into the four downstream nodes without a registry push.
Only the `ollama-runtime-metrics` container image in the Ollama Deployment was
patched. The existing `Recreate` strategy and 120-second shutdown grace period
caused a normal pod replacement. No inference, pull, unload or delete API call
was made by this validation.

The live mapping status reported three components and three serving relations,
both with `errorDetails: []`. API evidence identifies these components:

| Model | Component ID | Available disk size (bytes) |
| --- | --- | --- |
| `gemma:2b` | `120478897117245` | 1678456656 |
| `llama3.2:latest` | `272368005460306` | 2019393189 |
| `nomic-embed-text:latest` | `216208579417040` | 274302450 |

All three use cluster `suse-ai`, namespace `suse-private-ai`, service `ollama`,
and link to the existing service component `21793676483063`. Actual UI clicks
resolved the native service URN and a model URN containing `:latest`. The Models
overview returned HTTP 200, displayed all three rows and explicit `not reported`
request metrics, and had no JavaScript errors or failed requests. Model highlights
and the five-metric perspective rendered with numeric data. Detail navigation
also made 404 requests for absent saved `/api/perspectives/<identifier>` entries;
the default perspectives rendered successfully. These are recorded in the
browser evidence, not reported as topology errors.

The initial available-but-unloaded `llama3.2:latest` and `nomic-embed-text:latest`
samples were verified by evaluating their bound metric expressions with
PromQL `@ 1793898626`: loaded state and VRAM are 0, disk size is positive, and
loaded allocation/context are absent. Subsequent loaded observations keep the
same component IDs. The raw `/api/tags`, `/api/ps`, exporter exposition,
backend samples, bound queries, relations and screenshots were captured.

Before testing, Agent and Kubernetes - suse-ai were `Running` but already had
10 active error details each, with cumulative errors 79 and 34. After the live
check, both lists of active errors were byte-for-byte equivalent as parsed JSON,
and both counters were unchanged. This task does not claim the entire demo has
zero topology-sync errors.

Evidence is outside Git at
`/home/thbertoldi/suse/qa/ollama-models-3.0.1-20261105/`:
`ui-models.png`, `ui-serving-service.png`, `ui-model-highlight.png`,
`ui-model-metrics.png`, `model-values-verified.json`, `idle-model-values.json`,
`model-relations.json`, `*-mapping-final-live.json`, `sync-*.json`,
`stackpack-tests.log`, `exporter-tests.log`, `image-test.log`, and
`upload-upgrade.log`. Treat the evidence directory as private; share only the
named, reviewed artifacts. Temporary UI password/session copies were removed.

The original `registry.suse.com/ai/containers/suse/suse-ai-ollama-exporter:3.0.0`
reference was restored, and its rollout completed. All eight workload specs in
`suse-private-ai` and all six in `suse-ai-demo` match the pre-test snapshots,
including the complete Ollama Deployment spec. Temporary image-import helpers
were deleted, and the test image reference was removed from all four nodes.
`restoration-summary.json` and `image-changes.log` record the restoration.
The final sync descriptions still have the same 10 active details and unchanged
79/34 cumulative counters (`sync-comparison.json`). StackPack 3.0.1 remains
installed as requested; models stop refreshing after the exporter rollback and
will expire until exporter 3.0.1 is deployed again. No Git push/tag/PR or registry
push was performed.

## Pull request delivery

After validation and restoration, the user authorized pushing the branch and
opening a pull request. Implementation commit `422e9c1` is published in
[PR #64](https://github.com/SUSE/suse-ai-observability-extension/pull/64) against
`main`. The delivery changes only knowledge records; the uploaded 3.0.1 package
remains unchanged. The read-only delivery check again found both synchronizations
Running with the same active error details and cumulative counts.

## Table cleanup prepared for the same release

The subsequent [table review](OVERVIEW_TABLES_3.0.1.md) initially kept release 3.0.1 and
combines the shared model table's two availability columns into one, preserving
explicit `not reported` wording for unsupported metrics. It removes shared model
health from the table while leaving monitors and chart queries unchanged.
Ollama inventory and exporter source remain as validated above.

The cleanup was checked on the demo using temporary version
`3.0.2-dev.20261105.1`, then downgraded to the original installed 3.0.1. The
temporary catalog entry was removed. The modified release payload was not
uploaded as 3.0.1. After the initial local review, the user authorized delivery.
Table cleanup commit `35c3007` is pushed to the same branch, and PR #64's title
and description cover the Ollama inventory, exporter and table cleanup together.
