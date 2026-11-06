# SUSE AI 3.0 component model implementation

The demo is upgraded forward through unique `3.0.0-dev.N` packages with overwrite.
The release source remains version 3.0.0. No SA instance operations are used.

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
