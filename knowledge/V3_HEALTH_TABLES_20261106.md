# Health columns and model hosting: dev.8 → dev.9

This increment adds Health as the first column to all 33 SUSE AI overview
definitions, including the six menu tables, product views and related-resource
drilldowns. The cells use the component's actual health state. Missing health
remains UNKNOWN. Existing columns and explicit sorting are preserved; the GPU table
keeps Health, Node and GPU model fixed when scrolling. Views without explicit
sorting now use Health as their default sort column.

## Visible table changes

| Menu table | dev.8 | dev.9 |
|---|---|---|
| Overview | Name, Category, Service namespace, Cluster | Health followed by the same four columns |
| Applications & agents | Name, Service namespace, Category, Cluster | Health followed by the same four columns |
| Models | Name, Service namespace, Inference service, Product, Cluster | Health followed by the same five columns |
| Inference | Name, Service namespace, Category, Product, Cluster | Health followed by the same five columns |
| Data services | Name, Service namespace, Product, Cluster | Health followed by the same four columns |
| GPUs | Eleven node/capacity/telemetry columns | Health followed by the same eleven columns |
| Other SUSE tables and drilldowns | Existing identity or product columns | Health followed by the same columns |
| Native Open Telemetry tables | Existing native Health and other columns | Unchanged |

The six menu entries remain unchanged. This increment does not add another product
menu or change metric definitions.

## Why the model arrow changed

| Version | Relationship | Read it as |
|---|---|---|
| dev.6 and earlier serving previews | `ollama → llama3.2:latest` (`serves-model`) | Ollama serves the model |
| dev.8 | `llama3.2:latest → ollama` (`is-hosted-on`) | The model depends on its hosting engine |
| dev.9 | Same dependency direction as dev.8 | Same meaning; clearer model detail links and customer documentation |

The relationship describes the same hosting association from opposite perspectives.
The dependency direction supports inherited engine health. Direct model checks
retain precedence over the built-in derived-state monitor. Request flow is available
in traces; the hosting arrow does not claim that a model initiates an API call.

Model highlights now have a **Served by** component link. The previous **Related
services** section is titled **Hosting inference service**. Model/service identities,
the five hosting edges and their direction remain unchanged in this increment.
The package README and installed StackPack description explain the change for
customers upgrading from earlier previews.

## Verification

The live API returned a first, searchable/sortable Health column on all 33 SUSE
tables. All previous columns retain their definitions. The six menu tables retain
their explicit sorting. Four views with no explicit sorting now default to Health:
AI components (`common`), Model usage (`models`), Physical GPUs (`gpus`), and the
vLLM model view (`served-models-vllm`). CLEAR, DEVIATING and UNKNOWN cells were
observed; no missing state was converted to CLEAR.

The Models page shows four CLEAR served models. Model highlights resolve **Served
by → ollama** to the existing native service. Both native Open Telemetry overview
metadata objects match the dev.8 baseline exactly. Screenshots cover Overview,
Models, GPUs, a model detail, Services and Service instances before and after.

The native suite ran 105 tests with 17 opt-in backend tests skipped and no failures;
all 21 release tests passed. The native validator accepted 117 nodes and rejected
the invalid-CEL control. The initial local run caught an old assertion forbidding
Health on unresolved-call observations; it now permits the observation component's
own state without inferring server health.

All 68 monitor IDs and all five hosting-relation IDs/endpoints are unchanged.
Topology-sync list and every description report both synchronizations Running,
with the same ten pre-existing errors and identical details each as the baseline.
All 19 observed SUSE mapping statuses have empty errors; the two unobserved database
statuses remain 404.

Demo instance `261989587621111` remains INSTALLED at `3.0.0-dev.9`, uploaded once
and upgraded with overwrite. The archive SHA-256 is
`4daf24b4b193cf21b30ba09dc4d5ae3d1edde93ab7eebb20b8fa2be2935f8892`.
All 173 source package files match its staged payload except the manifest's
development version. No mapping, monitor, workload, icon or Collector definition
changed; no SA operation or older-state restoration occurred.

Private API captures, synchronization records and screenshots are under
`/home/thbertoldi/suse/qa/demo-v3-health-columns-n7t023_9/`. Open `comparison.html`
for the visual comparison, `health-tables-summary.json` for all 33 table results,
and `final-summary.json` for installation and preservation checks.
