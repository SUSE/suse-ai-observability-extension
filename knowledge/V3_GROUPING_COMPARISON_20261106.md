# Component and navigation increment: dev.6 → dev.8

The previous reviewed demo version was **3.0.0-dev.6**. This increment leaves
**3.0.0-dev.8** installed. Version 7 introduced the changes; version 8 assigned fresh
identifiers to the three hosting-dependency mappings after the backend continued
showing their old relation outputs. Each package was uploaded once with overwrite.

## Menu comparison

The SUSE AI menu has six entries instead of fourteen. No main-menu entry was added.

| Entry | dev.6 | dev.8 |
|---|---|---|
| Overview | Present | Present; same inventory columns |
| Applications & agents | Present | Present; entry point for application, agent, tool and registry services |
| Models | Present | Present; same inventory columns and model identities |
| Inference | Present | Present; entry point for Ollama, vLLM and LiteLLM |
| Data services | Present | Present; entry point for Milvus, Qdrant and OpenSearch |
| GPUs | Physical-device table | Restored full GPU-node table; node → Physical GPUs opens the device table |
| Ollama, vLLM, LiteLLM | Three additional product entries | Removed from the menu |
| Milvus, Qdrant, OpenSearch | Three additional product entries | Removed from the menu |
| MLflow, mcpo | Two additional product entries | Removed from the menu; reached through Applications & agents |
| Agents, Model usage | Component drilldowns | Still component drilldowns |
| Observed dependencies | Absent | Still absent; Unresolved calls remains on the caller |
| Four SUSE AI dashboards | Under Dashboards | Same four dashboards, unchanged |

Existing direct product-view URLs still resolve for saved links. Product metrics
remain in each product component's Highlights and Metrics pages.

## Table comparison

| Table | dev.6 columns | dev.8 columns |
|---|---|---|
| Overview | Name, Category, Service namespace, Cluster | Unchanged |
| Applications & agents | Name, Service namespace, Category, Cluster | Unchanged |
| Inference | Name, Service namespace, Category, Product, Cluster | Unchanged |
| Data services | Name, Service namespace, Product, Cluster | Unchanged |
| Models | Name, Service namespace, Inference service, Product, Cluster | Unchanged |
| GPU menu | GPU, Model, Node, Cluster; one row per physical device | Node, GPU model, GPUs, Memory / GPU, GPU utilization, Memory used, Temperature, Power, Host CPU usage, Usable host memory, Cluster; one row per node |
| Physical GPUs drilldown | Four-column device table was the main entry | Same device table, reachable from its node; device pages retain five hardware charts and allocation links |

The row distinction is intentional: the main GPU table restores node-level capacity
and host context. Physical UUID identities, workload allocations and device charts
remain available. Four GPU nodes and four physical devices were visible; all 24
bound GPU-table metric queries returned finite samples.

## Product component comparison

| Product/component | New navigation | Component detail changes |
|---|---|---|
| Ollama (`ollama`) | Inference → ollama | Existing runtime/model metrics retained; related served models now have a health dependency on Ollama |
| vLLM (`vllm-qwen-small-engine-service`) | Inference → service | Existing serving metrics and direct model-latency checks retained |
| LiteLLM (`litellm`) | Inference → litellm | Existing request, latency, token and gateway metrics retained |
| Milvus (`milvus`) | Data services → milvus | Existing search/request metrics retained |
| Qdrant (`qdrant`) | Data services → qdrant | Existing collections, vectors, request and memory metrics retained |
| OpenSearch (`opensearch`) | Data services → opensearch | Existing cluster, request and storage metrics retained |
| MLflow (`mlflow`) | Applications & agents → mlflow | Existing observed HTTP operation metrics retained |
| mcpo (`open-webui-mcpo`) | Applications & agents → service | Existing observed HTTP/tool operation metrics retained |

Native Open Telemetry service/instance icons and presentation contributions are
unchanged. Both native OTel overview metadata objects compare equal to dev.6.

## Logical and infrastructure component comparison

| Component | dev.6 | dev.8 |
|---|---|---|
| `demo-agent` (`genai agent`) | One Agent field, no highlight charts, UNKNOWN health; hosting/model-use links and scoped Traces tab | Health, Agent, Hosting service, Service namespace, Cluster and Metric scope fields; four hosting-service charts; derived CLEAR health; existing links and scoped traces retained |
| Other logical agents | Agent name, service links and scoped traces | Hosting identity and health fields plus a service dependency; demo-only charts require the explicit demo marker |
| Three Ollama served models | Inventory/runtime charts; no direct monitor or derived health | Existing charts plus a Health field and derived monitor; all three observed CLEAR from `ollama` |
| vLLM served model (`qwen-small`) | Two direct model-latency monitors | Direct monitors retained; new Health field and hosting dependency; direct observed health takes precedence |
| GPU node | Full hardware/host details existed but the main menu bypassed this table | Full table restored to the menu; new Physical GPUs related-resource link |
| Physical GPU | Device UUID/model, five hardware charts, node/pod links | Same device information and charts; accessible through its node |
| Model usage and unresolved calls | Caller-scoped measurements and links | Unchanged |

The four new `demo-agent` charts are **service tool calls**, **service tool duration
P95**, **service iterations per run**, and **service agent runs**. They use actual
reported metrics, aggregate the hosting service, and are labelled as including all
agents in that service. They do not claim per-agent attribution. Twenty matching
agent traces were returned in the captured one-hour query.

The built-in derived-state monitor applies to `genai served model` and `genai agent`.
Dependencies point from the logical component to its host. It follows the platform's
rule that direct observed health takes precedence, and does not treat missing
dependency observations as healthy. The native dry run returned four CLEAR checks:
three attributed to `ollama` and one to `agent-service`, without evaluation errors.
See the [official derived-state behavior](https://documentation.suse.com/external-tree/en-us/cloudnative/suse-observability/latest/en/setup/custom-integrations/monitors/derived-state-monitors.html).

All 67 pre-existing monitor URNs/numeric IDs are preserved. One derived-health
monitor is added; the 30 existing SUSE threshold monitors retain their definitions
and IDs. Monitor preview tooling now distinguishes controlled threshold previews
from a derived-health dry run.

## Appearance comparison

| Item | dev.6 | dev.8 |
|---|---|---|
| Outline icon intrinsic size | 40×40 | 16×16; drawing grid remains 40×40 |
| GPU view breadcrumb icon | Rendered 40×40 | Rendered 16×16 |
| Native component header icon | Platform-controlled size | Platform-controlled 18×18 in the captured agent/model pages |
| StackPack catalog logo | New outline artwork | Original SUSE chameleon/wordmark PNG restored byte-for-byte |
| SUSE AI menu-group logo | Outline artwork | Original SUSE logo embedded at navigation size; rendered 18×18 |

No ComponentType icon field changed. The SUSE asset retains its trademark status;
the original outline artwork remains Apache-2.0.

## Verification and evidence

The native suite ran 105 tests with 17 opt-in backend tests skipped, without failures;
all 21 release tests passed. The final mapping-name change also passed the six
focused model/dependency tests. Native validation accepted 117 nodes and rejected
the invalid-CEL control. Seven live table tests passed. All 30 threshold monitors
passed their three native preview states again; the new derived monitor was checked
against actual host health, without injecting production failures.

Final `sts topology-sync list` and every `describe` report both synchronizations
Running, with the same ten errors and identical active error details each as this
increment's fresh baseline. All 19 observed SUSE mapping statuses have empty error
details; the two unobserved database statuses remain 404. The final graph contains
five logical-component → host dependencies and no old `serves-model` or
`contains-agent` edges. All 173 package files match the deployed staging copy,
apart from the deliberately different development manifest version.

Private captures, API results and the visual comparison are under
`/home/thbertoldi/suse/qa/demo-v3-increment-grouping-du5l_g3e/`. `before/` is dev.6;
`after/` is dev.8. `comparison.html` embeds the before/after screenshots, including
both Open Telemetry inventories; their measurements and row counts remain live.
`verification-summary.json` records actual columns, fields, health, query results
and native OTel metadata equality; `final-summary.json` records deployment and
synchronization checks. Raw data and credentials
remain outside Git. The existing exporter and downstream workloads were unchanged;
no registry publication, SA operation or restoration of an older deployment occurred.
