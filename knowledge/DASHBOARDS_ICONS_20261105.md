# Native dashboards and original icons — lane A handoff

Verified on 2026-11-05, from base commit `7620efe`, branch
`wip/dashboards-icons`. This change adds files only. Lane B owns presentation
wiring, the StackPack logo reference, integration and deployment. Existing
markdown, `knowledge/CERTAINS.md`, the root Taskfile, presentations, ComponentType
icon fields and the version manifest remain unchanged. This new knowledge file
records the facts for later incorporation into `CERTAINS.md`.

## Native dashboard support checked first

Before creating the dashboards, the exact native dashboard at
`~/suse/suse-stackpacks/stackpacks/suse-virtualization/settings/dashboards/suse-virtualization-operations.sty`
was copied into an isolated copy of the current StackPack. The repository-pinned
validator accepted **97 nodes**: the existing 96 plus `_type: Dashboard`.
The reference file is not part of this change.

The validator image is pinned in `scripts/ci/stackpack-images.env`, digest
`sha256:237a6ffc5510c11b6e68aa0228365cac511b38a7d708df991e51bffa1f271b38`.
It runs locally with networking disabled. Final validation accepted **100 nodes**
and rejected the existing undeclared-CEL negative control.

AI Factory dashboards were inspected read-only using `sts dashboard describe
--context default --id <id>`:

| ID | Reference |
| --- | --- |
| `162159662254771` | AI Factory overview |
| `192359412882006` | Model serving |
| `213925202767249` | GPU fleet |

The adopted layout pattern is guidance, Right now stats, labeled trends and
hour-ago comparisons. The queries, copy, identifiers and SVG drawings here are
original. No AI Factory dashboard was changed or imported into the demo.

## Deliverables

| Native source | Scope |
| --- | --- |
| [overview.sty](../stackpack/suse-ai/settings/dashboards/overview.sty) | Gateway requests/failures, client p95 and call volume, vLLM output, Ollama residency and GPU utilization |
| [model-serving.sty](../stackpack/suse-ai/settings/dashboards/model-serving.sty) | vLLM finish rate, first-token latency and tokens; Ollama loaded models/VRAM; client duration and input/output tokens by caller/model |
| [gateway-spend.sty](../stackpack/suse-ai/settings/dashboards/gateway-spend.sty) | LiteLLM requests, failures, latency, reported spend and tokens by service/requested model |
| [gpu-fleet.sty](../stackpack/suse-ai/settings/dashboards/gpu-fleet.sty) | DCGM device count, utilization, temperature, framebuffer usage and power |

Each dashboard has an **About / How to read** block, four **Right now** stats,
four or five comparison charts, and contextual next steps. Each chart pairs
the same expression with `offset 1h` on every selector. All use a cluster
picker populated from observed metrics; there is no hard-coded cluster in the
shipped definitions. The dashboards link to each other using their stable
`urn:stackpack:suse-ai:shared:dashboard:<slug>` identifiers.

The source of truth is
[build_dashboards.py](../scripts/dashboards-icons/build_dashboards.py).
The `.sty` files are generated and checked for drift. Navigation uses the
dashboard route, independently of lane B's menu/presentation definitions.

The **17 original SVGs** in [icons/outline](../stackpack/suse-ai/icons/outline/)
cover every proposed menu entry, observed dependencies, inference server,
model, GPU, vector DB, search engine, gateway, agent, tool, registry, workflow,
UI and StackPack logo. All have intrinsic 40 × 40 dimensions, a 40 × 40 viewBox,
one 2-unit round stroke, `#30BA78` glyphs and `#E4F5EB` tiles. Sources, Apache-2.0
licensing and the menu/role mapping are recorded in the new
[LICENSES.md](../stackpack/suse-ai/icons/outline/LICENSES.md).

The gallery was rendered in Chromium and visually reviewed at 80, 40 and 20 px;
all 51 image instances loaded. Its HTML and PNG remain in the local evidence
directory. `preview` below regenerates it directly from the SVG sources.

## Verified metrics and interpretation

All demo reads used the supplied wrapper
`~/suse/qa/demo-native-stackpack-20261105-qOhD/sts`. A direct streaming return
from `Telemetry.instantPromql` produced HTTP 500 on this backend; collecting
the results with `.collectStream(...)` succeeded. The read helper uses that
form for all queries and never uploads settings or changes workloads.

An initial snapshot had Ollama, client GenAI and DCGM only. A subsequent
readback included vLLM and LiteLLM. The final inventory at **21:49:05 UTC** had
**134 current metric names**, 31 at one hour earlier, and 137 over the seven-day
lookback. The seven-day query uses `last_over_time` so metric names survive;
`count_over_time` loses them. These are observed names, not a declaration that
seven days of samples exist for every series.

The sanitized [metric inventory](DASHBOARD_METRIC_INVENTORY_20261105.json)
contains only metric names, series counts and query metadata. No user/key
labels, credentials, backend dashboard exports or raw responses are committed.
The **50 panel queries use 18 observed metric names**; the cluster picker also
uses the observed `ollama_api_up` gauge.

| Source | Interpretation enforced by the queries |
| --- | --- |
| Client `gen_ai_client_operation_duration_seconds_*` | Caller-side duration/count; no inferred attachment to an Ollama server or unique end-user request count |
| Client `gen_ai_client_token_usage_sum` | Histogram sum yields tokens; input/output labels remain distinct |
| vLLM `request_success_total` | All observed finish reasons are labeled **finished requests**, including `abort` and `error` |
| vLLM TTFT buckets / generation tokens | Server metrics remain separate from client and gateway observation points |
| Ollama loaded models / model VRAM | Loaded replicas and bytes, not persistent available-model inventory or request-side telemetry |
| LiteLLM counters / latency buckets | Rate first, then deduplicate scrape copies while preserving native dimensions and real serving replicas, then aggregate |
| DCGM gauges | Physical devices retain cluster, UUID and node; exclude missing UUIDs and MIG slices, deduplicate repeated pod/scrape copies |

Rate windows are five minutes. Error percentages require positive request
traffic: absence and idle traffic do not become a healthy zero. No panel uses
an unconditional `or vector(0)`. Empty histograms have no meaningful percentile.
The verified vLLM inventory did not report queue or KV-cache gauges, so there
are no speculative panels for them. The DCGM inventory did not report XID/ECC
metrics, so this dashboard does not claim that hardware errors are absent.

Framebuffer usage is `100 * used / (used + free)` using DCGM's matching MiB
gauges; reserved memory is outside that denominator. Power is watts. Spend / h
is `3600 * rate(litellm_spend_metric_total[5m])`, representing the reported
five-minute cost rate in LiteLLM's USD convention, not a bill or GPU cost.
Configured prices still need to be meaningful; zero reported spend does not
establish free infrastructure. LiteLLM documents the spend metric and request
latency in its [Prometheus reference](https://docs.litellm.ai/docs/proxy/prometheus)
and its USD cost accounting in [Spend Tracking](https://docs.litellm.ai/docs/proxy/virtual_keys#spend-tracking).

## Verification and its limits

| Check | Result |
| --- | --- |
| Native validator, then invalid-CEL control | 100 settings accepted; negative control rejected |
| Asset/PromQL/layout check | Four dashboards, 50 parsed/scoped queries, matched comparisons, valid navigation, 17 valid/licensed SVGs |
| Pinned Prometheus evaluation | Six scenarios passed: scrape duplicates, separate users/replicas, missing and idle traffic, reported failures, physical GPU identity, actual one-hour offset behavior |
| Live query execution | All 50 queries returned without execution errors; 41 returned samples |
| Expected empty live results | Seven hour-ago queries had no vLLM/LiteLLM history; two current vLLM TTFT queries had no observations. The label probe reported zero vLLM histogram observations. No synthetic traffic was generated. |
| Release/package/installer regressions | All 15 passed |
| Existing native contract suite | 35 passed, one asset-reference check failed, detailed below |
| Topology-sync list and every describe | Both Running; Agent/Kubernetes cumulative errors 79/34, ten active details each, byte-equal active-detail lists before/after |

`test_packaged_assets_are_referenced` requires every file in `icons/` to have
a `!icon` reference. The new 17 SVGs intentionally await presentation wiring;
the new licence document is metadata rather than an image. The same test run
on an isolated archive of unmodified base `7620efe` already fails for the
existing `icons/LICENSES.md`. The test was not weakened and no dummy references
were added. Lane B should wire the assets it adopts and reconcile documentation
files with that existing contract. This lane does not claim a fully green
native contract suite.

No native browser rendering of these new dashboards was performed: this lane
did not install them. Native validation, live query execution and local SVG
rendering are separate checks. No StackPack version was changed or uploaded.
The unchanged synchronization errors are pre-existing, not an error-free demo.

## Reproduce and integrate

The separate [Taskfile.dashboards-icons.yaml](../Taskfile.dashboards-icons.yaml)
keeps the existing Taskfile intact. `check` requires the pinned dependencies in
`tests/suse-ai/requirements.txt`; set `PYTHON` to that environment if necessary.

```bash
task -t Taskfile.dashboards-icons.yaml generate
task -t Taskfile.dashboards-icons.yaml check PYTHON=/path/to/native-tests/bin/python
task -t Taskfile.dashboards-icons.yaml query-test
task -t Taskfile.dashboards-icons.yaml validate
task -t Taskfile.dashboards-icons.yaml live \
  STS_BIN=/path/to/explicit/demo/sts EVIDENCE_DIR=/new/private/evidence/directory CLUSTER=suse-ai
task -t Taskfile.dashboards-icons.yaml sync STS_BIN=/path/to/explicit/demo/sts
task -t Taskfile.dashboards-icons.yaml preview OUTPUT=/new/private/icon-gallery.html
```

The read helper requires a new output directory. `inventory` accepts the same
wrapper and evidence arguments and records current, hour-ago and seven-day
metric-name inventories. The tasks contain no deployment operation.

Lane B can merge this additive branch, use `!icon outline/<name>.svg` in the
owned menus/presentations, select the new StackPack logo source, then validate
the combined package and browser behavior. A deployment must use a fresh
version and overwrite strategy under the standing repository rules.

Private evidence root:
`/home/thbertoldi/suse/qa/dashboards-icons-20261105-wxkdil_e/`.
It contains the three reference exports, reference/final validator logs,
`inventory-final/`, `live-final/`, query/release/native-contract/baseline test
logs, before/after synchronization descriptions, and `icon-gallery.html/png`.
