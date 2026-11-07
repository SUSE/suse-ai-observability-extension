# Install copy, model detail and dashboards: dev.96 → dev.99

This increment expands the installation description, exposes useful model inventory
details, reduces dashboard clutter, and brings all three requested Kubeflow products
into the demo. Versions 97, 98 and 99 are separate uploads with overwrite upgrades.
The release source remains 3.0.0. No SA instance or older demo state was restored.

Earlier navigation, GPU-table and model-health changes are recorded in
[the grouping comparison](V3_GROUPING_COMPARISON_20261106.md) and subsequent reports.
This comparison starts from the already reviewed dev.96 state.

## What changed

| Area | dev.96 | This increment |
| --- | --- | --- |
| Installation overview | A brief feature list | Operational value: response latency, model availability, usage and GPU capacity; connected application-to-model context |
| Installation details | Mostly configuration and limitations | Questions an operator can answer, concrete product capabilities, views and dashboards, then telemetry boundaries |
| Configuration page | Attribute rules first | Prerequisites and a three-step quick start, followed by identity and migration guidance |
| Ollama model About | Health and hosting engine | Family, reported parameter size, quantization, loaded replicas, current VRAM and disk size in GiB, plus inventory explanation |
| Ollama model Highlights | Three mostly flat inventory charts | Two useful residency histories: loaded state and VRAM. Disk size is a compact current field and remains available under Metrics |
| vLLM model Highlights | Three latency charts | First-token latency, request latency and generated-token throughput; the other metrics remain under Metrics |
| Model usage | Identity and a largely empty landing page when only traces exist | A concise metric-scope field and an explicit **Inspect model calls in Traces** action using the exact component filter |
| Relationship heading | Generic service wording | **Hosting inference engine** on deployments; **Calling application** on usages |
| Inventory link | Generic models wording | **All model deployments**, accurately naming the existing destination |
| Aggregate hour comparisons | Pale Now, darker history | History first and pale; Now second and dark when both periods have data |
| Per-entity charts | Current/history pairs for every caller, model, replica or GPU | Current-window trends; aggregate comparisons retain the hour-ago comparison without duplicating every legend |
| GPU and replica legends | Full UUIDs and repeated period names | Short display identities; full identities remain in query grouping and deduplication |
| vLLM p95 explanation | No histogram-resolution explanation | Explains why a percentile can remain flat while individual requests vary |
| Kubeflow | No deployed Pipelines, KServe or Model Registry | All three deployed, real Iris lifecycle completed, existing demo registry/prediction scenarios enabled |

The six main menu entries are unchanged: **Overview**, **Applications & agents**,
**Models**, **Inference**, **Data services**, and **GPUs**. No individual product menu
returns. Shared tables retain Health and their existing identity columns. The GPU
node table retains all 17 columns and four nodes; physical devices remain a drilldown.
No component type, monitor ID, relation direction or native service icon changed.

Milvus, Qdrant, OpenSearch, LiteLLM, MLflow, mcpo, logical agents and physical GPU
component definitions are unchanged by this increment. Their existing telemetry
and product sections remain available. Kubeflow introduces live service instances
through the existing mappings, not additional component types.

## Feedback checked against real data

**The 59 ms vLLM p95 is a histogram estimate, not display rounding.** The captured
hour has 77 observations, all in the 40–60 ms bucket. Histogram interpolation gives
59 ms at all 61 sampled points, while the measured mean varies from approximately
43.34 to 44.72 ms. Changing chart precision cannot recover individual durations
from those buckets. The dashboard now explains this and includes output throughput
for a complementary activity signal.

**Five model usages legitimately have traces without GenAI metrics.** The direct
Traces action was exercised in the browser and showed 35 matching calls for the
reviewed LiteLLM/qwen-small usage. Queries retain namespace, caller, provider, model
and endpoint identity; unrelated metrics were not substituted to fill empty charts.

**One additional retained usage remains unexplained:** component `183022976899565`,
`product-traffic` / `litellm` / `vllm-chat`, with no endpoint. Its sole source is the
model-metrics mapping. Exact GenAI metric and trace queries returned no matches over
24 hours, including the precise legacy-provider fallback. Its mapping has a
15-minute expiry, but the exposed source metadata does not establish why it remains.
Span aggregates omit endpoint dimensions and cannot prove an identity-equivalent
replacement. No component was deleted or data fabricated to conceal this finding.

**Raw type names are controlled by this platform version.** The installed UI builds
titles from the canonical type name, and related-resource counts from the returned
component types. Presentation titles do not override `(genai served model)` or
`1 otel service`. Useful headings and direct named links improve navigation without
renaming canonical types or altering native Open Telemetry pages. Removing all
related resources was tested in dev.97 and produced a misleading empty card; dev.98
restored the relationships. dev.99 shortens the scope text that the narrow About
column clipped.

The installed dashboard renderer ignores per-query color/style options. Ordering
two aggregate series works with its fixed palette. Per-entity charts use current
trends because the palette cannot reliably pair current/history colors for an
arbitrary number of entities. If history is absent, Now can receive the first palette
color; absence is not filled with fabricated history.

## Kubeflow deployment and live validation

The initial absence was confirmed using namespaces, CRDs and workload snapshots.
The deployed chart is the local SUSE Kubeflow 0.4.0-alpha.1: Pipelines 2.17.0,
KServe v0.19.0 and Model Registry Hub v0.3.10, with required Istio/Knative/profile
infrastructure. Controllers are in `kubeflow`; the Iris predictor is in
`kubeflow-user-example-com`. A separate `kserve` namespace is not required.
Existing cert-manager and AI products were preserved. Both new storage claims are
Bound using the explicitly selected `local-path` class.

The first pipeline exposed a chart omission: the API server was 2.17.0 but generated
workflows used `ghcr.io/kubeflow/kfp-driver:latest`, which required a newer flag.
`demo-kubeflow-pin-driver` sets `V2_DRIVER_IMAGE` to 2.17.0 at digest
`sha256:887c1f6a730df9992bae1f57b7ddf509491c75fb94d03bb9a7865384ce6cde43`.
This pin must be retained after future chart upgrades until the chart supplies it.

The branch-built Iris image,
`local.invalid/suse-ai-iris-pipeline:demo-20261107-0252`, was imported into all four
RKE2 nodes without a registry push. Pipeline run
`145c64c9-e2e8-4552-8c03-d4fee883621f`, workflow `iris-lifecycle-vwjcs`, succeeded:
prepare → train → quality gate → register → deploy → prediction smoke test.
Training accuracy was 0.9473684210526315; registry model version ID was 2.
The predictor reached Ready and returned HTTP 200. Existing `traffic-gen` now enables
Kubeflow scenarios; actual agent calls returned HTTP 200 from both registry and
prediction endpoints.

The Collector retains its published 0.164.1 digest and all seven existing profiles,
credentials and CA mounts. An additional profile scrapes the Pipelines API, Argo
workflow controller, KServe controller and predictor with real pod identity. The
existing authenticated registry probe discovered the new registry. The complete
Collector configuration passed validation using the deployed image before rollout.
These demo manifest additions are captured privately and must be retained during
future Helm reconciliation; they are not a new Collector release.

All **12 monitor queries returned finite live inputs** without changing their
definitions. Prediction p95 was approximately 4.75 ms in the first populated sample.
All 12 monitors also passed **36 preview checks** across failing, recovering and
no-data states. Those previews do not inject telemetry or persist health.
Original-query dry runs bound checks to the actual new services. They observed the
failed initial workflow and a KServe status-update conflict during startup; these
events remain in history rather than being cleared manually.
The later original-query dry runs returned **CLEAR for all 12 checks** after the
failure windows expired. Six pipeline traces were returned by the scoped backend
query. The final five-minute Collector log capture contains no error-level records.

## Validation and review evidence

- Native suite: 109 tests, 18 opt-in checks skipped, no failures; release suite:
  24 passed. The final memory-field changes also passed all seven Ollama tests,
  including real-Prometheus scope, replica, absence and GiB scenarios.
- Seven dashboard query scenarios passed, including full identity preservation
  when short display labels collide. Four dashboards contain 39 scoped parsed
  queries using 18 metric names; all 17 SVG assets pass the existing checks.
- Native package validation accepts 118 nodes and rejects the invalid-CEL control.
  No Groovy source changed. All 69 monitor IDs remain unchanged.
- Native Open Telemetry Services and Service instances overview metadata compare
  equal to the earlier verified baseline. Shared-table definitions are unchanged.
- `sts topology-sync list` and every `describe` show Running. The initial/final
  captures retain 10 Agent errors and 33 Kubernetes errors with identical returned
  details. All 19 observed SUSE mapping statuses have empty error details; the two
  unobserved database mapping statuses remain 404. This is not a clean-backend claim.

Private evidence root:
`/home/thbertoldi/suse/qa/demo-install-model-dashboard-06iwiqou/`.
It includes [before/after screenshots](</home/thbertoldi/suse/qa/demo-install-model-dashboard-06iwiqou/comparison.html>),
the [adversarial dev.98 review](</home/thbertoldi/suse/qa/demo-install-model-dashboard-06iwiqou/adversarial-ux-dev96/after-dev98/REVIEW.md>),
raw histogram samples, monitor inputs/previews, lifecycle logs, configuration
backups and deployment records. Raw captures and credentials remain outside Git.
The [final dev.99 check](</home/thbertoldi/suse/qa/demo-install-model-dashboard-06iwiqou/adversarial-ux-dev96/after-dev99/REVIEW.md>)
confirms the short model-usage scope text fits and its related-resource and Traces
links remain intact.
Expanded installation details are verified by source and package/API content;
an unobscured expanded-details screenshot is not claimed.

## What to inspect

1. **StackPacks → SUSE AI → Read more**: value description and product coverage.
2. **SUSE AI → Models → llama3.2:latest / gemma:2b**: metadata, readable memory,
   loaded versus unloaded state, hosting engine and residency history.
3. A model usage reached from its calling service: **Inspect model calls in Traces**.
4. **Dashboards → SUSE AI — Model serving / GPU fleet / Overview**: shorter legends,
   current trends, aggregate hour comparisons and the histogram explanation.
5. **SUSE AI → Applications & agents**: `kubeflow-pipelines`,
   `kubeflow-workflow-controller`, `kubeflow-pipelines-demo`, and
   `kubeflow-model-registry`; **Inference**: `kserve-controller` and `sklearn-iris`.
