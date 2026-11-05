# AI overview table cleanup — 3.0.1

This ships with the Ollama available-model inventory and exporter on
`feat/ollama-model-inventory-3.0.1` (implementation base `422e9c1`). StackPack and
exporter release versions remain **3.0.1**. The combined PR is the existing
[PR #64](https://github.com/SUSE/suse-ai-observability-extension/pull/64).
Table cleanup commit `35c3007` has been pushed to that branch, and PR #64 now
includes the combined description and links to this evidence.

## Behavior

Overview includes native services and served models. Data services includes
only native `otel service` components classified as vector databases or search
engines. Caller-scoped observations have a dedicated **Observed dependencies**
menu and table: name, **Client-observed; unresolved** Discovery cell, product,
calling-service link, caller namespace and observed-from cluster. A missing
observer cluster reads `Not reported`. Observations have no server health or
server metric columns.

The Collector association behavior is preserved: verified calls connect the
caller directly to the native data service. The old unresolved observation
stops refreshing and expires after 15 minutes. The caller's **Data dependencies**
section links to those outgoing native neighbors; its separate **Observed
dependencies** section lists unresolved caller-scoped observations. No endpoint
string matching is introduced, and resolved observations are not retained as
second permanent representations of native services.

Data services keeps health, name, service namespace, product and cluster, plus
a **Key metrics** link to the native component's existing product highlights.
Milvus links to search latency/request rate, Qdrant to collections/response
rate, and OpenSearch to cluster health/pending tasks. These are navigation
links, not new numeric aggregations across incompatible product metrics.

Models and Model deployments combine two availability columns into one:
`Residency; server requests not reported` for Ollama,
`Server requests; residency not reported` for vLLM, and `not reported` otherwise.
Shared model health is removed because Ollama models have no attached model
monitor. Logical Agents also lose their unknown health column and gain a
hosting-service link. Monitors and product charts remain unchanged. Native
service and caller model-usage health stay visible.

Applications and Model usage already had populated, relevant fields. Inference
loses an undefined K8s namespace reference that the installed backend already
omitted. Service namespace remains to distinguish native identities.
Presentation composition operates at query level, so observer columns belong
to the dependency presentation. See the
[official schema](https://integration.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/presentation/schemas-ref.html).

## Screenshots and column audit

These are actual Chromium captures. “After” uses the temporary review version.
Most “before” captures precede the upgrade; Overview was recaptured from the
restored original 3.0.1 after correcting a login redirect race in the harness.
Its original and restored API column metadata match. Health and metric values
can change between captures.

| Table | Before | After | Result |
| --- | --- | --- | --- |
| Overview | [Screenshot](evidence/3.0.1-tables/overview-before.png) | [Screenshot](evidence/3.0.1-tables/overview-after.png) | 7 → 5 columns; exclude observations and observer fields |
| Inference | [Screenshot](evidence/3.0.1-tables/inference-before.png) | [Screenshot](evidence/3.0.1-tables/inference-after.png) | 6 → 6 rendered columns; remove unused namespace reference |
| Data services | [Screenshot](evidence/3.0.1-tables/data-services-before.png) | [Screenshot](evidence/3.0.1-tables/data-services-after.png) | 9 → 6; native rows; remove observer fields, constant Discovery, redundant Category; add metric link |
| Applications & agents | [Screenshot](evidence/3.0.1-tables/applications-before.png) | [Screenshot](evidence/3.0.1-tables/applications-after.png) | Keep all 5 populated columns |
| Models | [Screenshot](evidence/3.0.1-tables/models-before.png) | [Screenshot](evidence/3.0.1-tables/models-after.png) | 8 → 6; remove shared health, combine availability columns |
| Model usage | [Screenshot](evidence/3.0.1-tables/model-usage-before.png) | [Screenshot](evidence/3.0.1-tables/model-usage-after.png) | Keep 7; request rate/tokens populated on all six rows, latency on five |
| Agents | [Screenshot](evidence/3.0.1-tables/agents-before.png) | [Screenshot](evidence/3.0.1-tables/agents-after.png) | 4 → 3; remove unknown health; link hosting service |

The [new Observed dependencies table](evidence/3.0.1-tables/observed-dependencies-after.png)
has six columns; the baseline had no standalone overview. The
[RAG highlight](evidence/3.0.1-tables/rag-ui-after.png) shows one native Data
dependency. Clicking its count opens the
[scoped native table](evidence/3.0.1-tables/rag-data-dependencies-after.png), and
clicking Milvus reaches the [native component](evidence/3.0.1-tables/native-milvus-ui-after.png).

The demo had eight overview rows, one inference service, one native data
service, five applications, six model usages and one logical agent. Models and
Observed dependencies were empty during this check: exporter 3.0.0 had already
been restored after the earlier Ollama test, and the Milvus association had
already resolved. These two screenshots verify empty-state layouts, not
populated live rows. Their cell values/identities are checked with executable
CEL fixtures; populated Ollama evidence is in
[OLLAMA_MODEL_INVENTORY.md](OLLAMA_MODEL_INVENTORY.md). No synthetic telemetry
or workload changes were used to populate screenshots.

[Table metadata, counts and browser results](evidence/3.0.1-tables/table-summary.json)
record the seven comparisons. All eight updated views returned HTTP 200 with
no page errors or failed requests in the successful capture run.

## Tests

| Check | Result and output |
| --- | --- |
| Native mapping/query/Collector/contracts | 75 passed; 13 opt-in fixture checks skipped — [full output](evidence/3.0.1-tables/tests.log) |
| Release/package/installer | 15 passed — same full output |
| New presentation checks | Two CEL identity tests and three read-only backend tests passed — [output](evidence/3.0.1-tables/presentation-live.log) |
| Exporter HTTP / sidecar patch | 11 + 2 passed — [output](evidence/3.0.1-tables/exporter-test.log) |
| Pinned native validator | 96 settings accepted; undeclared-CEL negative control rejected — [output](evidence/3.0.1-tables/validation.log) |
| Repository/package | `git diff --check` passed; review payload matched source except the temporary version |

Backend tests verify exact ordered columns for all eight tables, exclude
observation identifiers from native inventories, resolve actual agent/model-
usage service links, and evaluate the backend's bound dependency section.
That section returned Milvus `112869539086775` for RAG `267074156912894`.
The empty Models page does not constitute a live model-link test; the earlier
Ollama validation covers that populated case. Telemetry-injection fixture
tests remain opt-in.

```sh
task stackpack-presentation-test PYTHON=.resources/native-tests/bin/python
# To enable read-only backend checks, also set:
# AI_PRESENTATION_URL, AI_PRESENTATION_TOKEN_FILE, AI_PRESENTATION_EVIDENCE
# AI_PRESENTATION_CALLER=<known caller with a resolved native data dependency>
```

## Demo lifecycle

`task stackpack-review-package REVIEW_VERSION=3.0.2-dev.20261105.1` staged a copy
without editing the release manifest. The temporary version was uploaded once
and installed with `--unlocked-strategy overwrite`. Archive SHA-256:
`6e71f3f2797ad46564885409f67d4f652e107ba5cbdf021e76342e6af8275e41`.
Do not reuse this review version, even after its catalog entry is removed.

The native-schema downgrade restored the already-uploaded **3.0.1**, retaining
instance `197048877569388` and status `INSTALLED`. The temporary catalog entry
was then deleted. [Before](evidence/3.0.1-tables/instances-before.json),
[review](evidence/3.0.1-tables/instances-review.json),
[restored](evidence/3.0.1-tables/instances-restored.json), and
[final catalog](evidence/3.0.1-tables/versions-restored.json) document this.
All seven original table schemas matched the restored API results. The demo
ends on its original layout; the release branch contains the cleanup.
No modified payload was reuploaded as 3.0.1.

The final local release archive `dist/suse-ai-3.0.1.sts` was rebuilt with
`task stackpack-package` ([output](evidence/3.0.1-tables/release-package.log)).
SHA-256: `767c1d100f4c25d4a1fe39cbc62704ea5abc5dcf93ca2c848d565f6bc7db3008`.
It contains the cleanup and has not been uploaded to the demo catalog.

`task stackpack-sync-status` listed and described both synchronizations before,
during and after review. Agent and Kubernetes - suse-ai remained Running,
with unchanged cumulative errors 79/34 and identical lists of ten active error
details each. [Comparison](evidence/3.0.1-tables/sync-comparison.json) records
the counters and hashes. This is not an error-free backend claim. The Collector
overlay and workloads were not modified. Temporary UI credentials were removed.

Raw private API responses, settings backup, browser harness and lifecycle logs
remain at `/home/thbertoldi/suse/qa/table-cleanup-3.0.1-20261105/`. Only reviewed
screenshots, test output and metadata are included here. Table-only and
combined-branch patches and the revised PR description are under `.resources/`
for local review before pushing.
