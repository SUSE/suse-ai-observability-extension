# SUSE AI 3.0 component model implementation

The demo is upgraded forward through unique `3.0.0-dev.N` packages with overwrite.
The release source remains version 3.0.0. No SA instance operations are used.

The latest increment leaves **3.0.0-dev.9** installed, with Health first on all SUSE
tables and clearer model hosting links. See the
[dev.8 → dev.9 comparison](V3_HEALTH_TABLES_20261106.md).
The preceding [dev.6 → dev.8 comparison](V3_GROUPING_COMPARISON_20261106.md) records
grouped navigation, the restored GPU table and SUSE logo, smaller navigation icons,
hosting-service health and agent details. The sections below record earlier
iterations at the versions where they were verified.

## Product views and OTel overlays

Iteration 1 was verified on demo Observability 2.11.1, Open Telemetry 0.1.4 and
Collector 0.164.1. Development version 2 established a native control by excluding
SUSE presentations from OTel service/instance components. Version 3 introduced the
redesign; version 4 made the overview column/filter definitions self-contained.
At specificity 1, a column reference alone did not inherit our common definition
on this backend. The explicit definitions fixed the missing identity columns.

Shared tables now show identity only. The eight product entries under SUSE AI
show their own measurements: vLLM, Ollama, LiteLLM, Milvus, Qdrant, OpenSearch,
MLflow and mcpo. All 31 table metric queries returned live samples at verification.
MLflow and mcpo use the observed SDK HTTP operation histograms, independently of
endpoint availability probes. Ollama showed three available models and two loaded
copies. Model names remain available even when not loaded.

OTel component contributions have specificity 1 and no icon, summary, title or
trace override. Explicit inventory presentations remain separate from component
overlays. Presentation field, section, metric, resource, column, filter and tab IDs
use `suse_ai_`. Unresolved calls are a related-resource section on the caller; the
Observed dependencies menu entry is removed. Native mappings contain no unsupported
domain/layer assignment fields. vLLM queries also accept the observed 0.19 metric
names for KV cache and per-output-token latency.

Both Open Telemetry overview metadata objects (Services and Service instances)
compare equal to the native control. The 34 component identities present in both
captures retain their native icon, fields and relative order, metric sections,
summary, resources, events and trace bindings. Changing health, labels and language
values are live data and excluded from the structural comparison. All 67 monitor
URNs and numeric IDs are unchanged from development version 1.

Verification: 97 native tests (16 opt-in checks skipped), 21 release/deployment
tests, seven live table tests, native schema/CEL validation and its rejected negative
control. Topology-sync list and every description remain Running with the baseline
79/34 cumulative errors and ten active details each. Observed SUSE mappings report
no errors; unresolved database mapping status remains 404 when there are no inputs.

Private evidence: `/home/thbertoldi/suse/qa/demo-v3-iterations-1-2-20261106-v3k4wh25/`.
The `control/` and `iteration1-fixed/` directories contain before/after Services,
Service instances and Ollama screenshots. `native-comparison-iteration1-fixed.json`
records the comparison, and `product-tables/` records all eight tables and their
actual bound-query results. Raw data and credentials are not packaged or committed.

## GPU devices, dashboards and monitor guidance

Iteration 2 merged local branch `wip/dashboards-icons` and shipped the GPU device
spike as normal package settings. Development version 5 introduced these settings;
version 6 compacted the dashboard layout. The final demo instance is
`261989587621111`, version `3.0.0-dev.6`, status `INSTALLED`, configuration `{}`.
Every development version was uploaded once and every upgrade used overwrite.
No older demo state was restored.

SUSE AI → GPUs contains four physical Tesla T4 devices, keyed by cluster and UUID,
with four node relations and two workload allocation relations: Ollama and vLLM.
Allocation uses workload datapoint labels, not the exporter pod. A device exposes
utilization, temperature, used/free framebuffer bytes and power, plus links to its
node and allocated pods. MIG-labelled samples are excluded from physical discovery;
that exclusion has executable CEL coverage, but this demo has no MIG hardware.
The existing NVIDIA XID monitor retains its node binding and identifier.

The four dashboards are under Dashboards → SUSE AI — Overview / Model serving /
Gateway & spend / GPU fleet. All 50 current and one-hour-offset panel queries
returned finite live samples. Six Prometheus query scenarios passed. The 17
original outline SVGs are wired to SUSE menus and SUSE-owned components; native
OTel icons are preserved. No ComponentType icon field changed.

All 30 existing monitors now use Check first / Likely causes / Fix / Verify
guidance, component/metric links, and contextual check titles. Four model monitor
queries preserve service/model labels in their aggregations so titles resolve.
All 67 monitor URNs and numeric IDs match the post-reinstall development-version-1
baseline. The approved Iteration 0 reinstall had changed the 30 SUSE numeric IDs;
no subsequent upgrade changed them.

Each monitor's original PromQL was exercised against failing, recovering and absent
metric fixtures in Prometheus. Separately, `task demo-monitor-test` exercised the
installed native monitor function in all three states using controlled query
inputs: 90 previews passed. No-data returned zero check states, not a healthy
result. The original installed queries also ran in dry-run mode, producing 42
checks with no evaluation errors. These tests did not inject production failures,
ingest synthetic telemetry or persist test health states.

## Final verification and review

The final native suite ran 104 tests with 17 opt-in backend tests skipped; all
remaining tests passed, including the complete monitor query matrix. All 21
release/deployment tests passed. The seven live table checks were then run
separately against version 6 and passed. The native validator accepted 115 nodes
and rejected the invalid-CEL control.

The final Services and Service instances overview metadata match the native
control exactly. All 33 component identities present in both final/control
captures retain the native presentation structure; live values can change.
`control/` contains the native before screenshots, `final/` contains the final
screenshots, and `native-comparison-final.json` records the comparison. The
original `before/` capture is also retained: that older SUSE presentation was
already overriding native OTel content, which the new overlays correct.

Final topology-sync list and every description remain Running. Agent/Kubernetes
cumulative errors are still 79/34, with the same ten active details each as the
baseline. Observed SUSE mappings have empty error details, including GPU counts
4 devices / 4 node relations / 2 workload relations. The two unobserved database
mapping status endpoints still return 404. A missing saved perspective also
returns 404 in component navigation; the component content and links render.

The private evidence directory contains `REVIEW.md`, before/after screenshots,
`final-verification/`, `final-product-tables/`, `monitor-previews-3/`,
`dashboard-live/`, and `navigation-verified/`. Review SUSE AI → Models for the
three available Ollama models and `qwen-small`; the eight product menu entries for
their real measurements; GPUs for device-to-workload navigation; and a service's
Highlights → Monitors → monitor definition for the installed remediation text.
The observed CLEAR status panel displays metric/threshold evidence and omits the
remediation section. No SA operation or registry push occurred.
