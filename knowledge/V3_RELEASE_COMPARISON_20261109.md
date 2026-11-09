# Product icons, release comparison and health coverage — 2026-11-09

The new demo retains the development SUSE AI instance and adds a separate copy of the published GitHub `v3.0.0` for comparison. The published tag is `03a8701a0289525a2038d0c2653c2e2068058260`; it was not moved or replaced. Only the newly supplied demo was changed.

The development menu is **SUSE AI**. The comparison menu is **SUSE AI 3.0 release** (`suse-ai-v300`). Both have live telemetry. The comparison's development packaging version identifies the isolation adapter, not a different upstream release. Final installed versions are **3.0.0-dev.997** for development (after the icon-scope clarification below) and **3.0.0-dev.996** for the release comparison. Both are INSTALLED; the original development instance ID `198933190161282` is preserved, and the comparison instance is `124073120293639`.

## Icons and native pages

The user authorized custom icons for recognized products and clarified that generic OpenTelemetry services must retain their native icons. Thirteen product-specific, icon-only presentations remain; the catch-all AI service icon and ten category-based overrides are removed. An AI category alone does not replace the native service or instance icon. Product logos are restored from the published release; mcpo uses the original tool glyph. All overrides require the `stackpack:suse-ai` label and an explicit supported `suse.ai.product` match.

The product drawings retain their original viewBoxes within a light-green tile. Intrinsic dimensions are 16×16. The tile fixes a dark-header contrast issue caught during review; the UI renders the header image at 18×18 and the body image at 16×16. The supplied SUSE chameleon remains the menu icon. ComponentType `iconbase64` fields were not changed.

Native Services columns and layout remain unchanged. Ollama's fields, highlight metrics, links, related resources, actions and type are unchanged; its resolved icon changes intentionally. [Presentation composition](https://integration.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/presentation/concepts.html) supports partial contributions; the preservation result here was also checked against actual before/after API responses and screenshots.

### Follow-up verification: product-only overrides

Development `3.0.0-dev.997` was uploaded once and overwrite-upgraded in place. The release comparison remains on `.996`. The native validator accepts 132 settings and rejects the invalid-CEL control; seven local presentation/overlay checks pass, with five opt-in live table tests skipped. All 190 packaged files match the working source apart from the staged development version.

Before/after component API checks covered 69 surviving services and instances: 22 regained native icons, 40 retained their product icons, and seven native controls were unchanged. One short-lived training instance expired between captures. Product labels without a configured icon, such as `pytorch`, also retain native icons. Highlight metrics, links, related resources, actions and type names compare equal; seven components' field differences are live values, labels or health states.

All 21 observed SUSE mappings return empty error details. Both topology synchronizations remain Running; Agent retains its baseline 75 errors and Kubernetes has zero. Evidence is under `/home/thbertoldi/suse/qa/product-icons-20261109-pkg62gr7/`, with the immutable upload and validator receipts in the shared deployment ledger's `3.0.0-dev.997/` directory.

## Released 3.0.0 versus development

| Area | Published 3.0.0 comparison | Development |
| --- | --- | --- |
| Navigation | Overview, Applications & agents, Models, Inference, Data services, GPU infrastructure | Same first five groups; GPUs replaces GPU infrastructure |
| Overview | Health/name/category/namespace/cluster plus calling-service and observed-cluster columns | Health/name/category/namespace/cluster only |
| Applications & agents table | Health, name, namespace, category, cluster | Same identity columns; logical agent and RAG activity sections have real demo signals |
| Models table | Served vLLM model; shared latency/first-token/output columns | Three available Ollama models plus vLLM; health, identity, engine, product and cluster; product-specific detail metrics |
| Inference table | Health, identity, category/product, cluster and Kubernetes namespace | Health and shared identity; detailed product metrics stay on the appropriate component |
| Data services table | Includes discovery and client-observed dependency columns | Health, name, namespace, product and cluster; unresolved calls appear on their calling service |
| GPU table | 12 columns, including GPU memory used, CPU and usable host memory | 17 columns, adding family, OS/version, CUDA, driver and memory utilization; physical GPU components and workload links |
| Service/instance details | Released high-specificity presentation, product icons and original fields | Native detail composition plus namespaced product metrics, compact custom icons and clearer related-resource labels |
| Served models | One vLLM model in this live data; two direct latency checks | Same vLLM model plus three Ollama inventory models with direct availability checks |
| Model usage | Separate caller/model/provider/endpoint observations and two direct checks | Same identity concept; scoped traces and improved detail guidance; trace-only usage is not presented as metric health |
| Logical agent | Released containment relation; no packaged derived-health monitor | Agent-to-host dependency, derived health and observed activity metrics |
| GPU components | Native GPU nodes/workload views; no physical-device component | Four physical devices related to four native nodes; device health remains UNKNOWN without a suitable health signal |
| Observed database dependency | Distinct observed endpoint plus calling-service/discovery columns | Endpoint retained; exposed as an unresolved call on the caller rather than a separate menu |
| Dashboards | No packaged native dashboards in this tag | Overview, model serving, gateway spend and GPU fleet |
| Pack-owned monitors | 30 | 33 after restoring application operation reliability |

The shared tables all retain Health. The old and new menu names are similar because the published tag already grouped products; the comparison does not claim that this grouping was newly introduced by this increment.

## What the 2.0 health audit found

The GitHub `v2.0.0` ref is `cff6fc5e3ac9215d2e8c7c5d0b8134c50a61a06b`. The local tag pointed elsewhere and was preserved; the published ref was fetched into a separate comparison ref. The saved initial 2.0 installation from this new demo also contains the same sixteen SUSE monitor identifiers.

| Coverage | Published/saved 2.0.0 | Released 3.0.0 | Current development |
| --- | --- | --- | --- |
| SUSE monitor definitions | 16 | 30 | 33 |
| vLLM latency | Two latency checks target the inference product | Two latency checks target each served model | Same direct model checks |
| vLLM capacity | Queue and GPU-cache checks on the product | Canonical inference service | Same |
| Ollama model availability | No direct model check found | No direct model check | Fresh model inventory/API check; unloaded is valid |
| Model usage | No separate model-usage checks | Exact-scope latency and reliability | Same |
| Logical agent inheritance | No configured model/agent derived monitor found | None | Agent inherits host/dependency health |
| Application errors | All span kinds, >5%, legacy service-name identity | Native OTel checks cover incoming spans | Restored all-operation check plus native incoming checks |
| Product checks | Milvus 3, Qdrant 4, OpenSearch 2, GPU XID 1 | Same plus 12 Kubeflow/KServe/registry checks and HTTP availability | Retained, with customer-facing descriptions |

The audit does not disprove differently configured health propagation in a previous environment. Health fields and hosting relations alone do not establish an active inheritance monitor. The saved initial installation's derived monitor targets Kubernetes workloads, not models.

A real regression was found: native OTel reliability checks filter SERVER/CONSUMER spans. Client-only `product-traffic`, `traffic-gen` and `pytorch-training` had no check even though their operation metrics existed. **AI application operation reliability** restores the old all-span scope at the 5% threshold, now qualified by namespace and service. Its selector includes unclassified AI application services. The nine live checks include those three workloads, Open WebUI, `llm-service`, `agent-service` and the three RAG apps. Existing thirty-two SUSE monitor IDs are preserved.

No telemetry or zero traffic produces no check. This measures failed traced operations, not endpoint uptime or unique user requests. The new query passed failing/recovering/no-data fixtures, CLIENT/INTERNAL/SERVER cases, successful traffic without an error series, idle traffic and identity-isolation cases. Native previews exercised failing, recovering and no-data states without persisting synthetic health.

GPU device health is still UNKNOWN: current XID inputs are absent, and the existing XID monitor targets Kubernetes nodes. Trace-only model usage and observed database endpoints also do not establish direct health. Direct model latency/inventory health does not mean full inheritance of every inference-engine failure.

## How the comparison is isolated

The builder retains all 93 released SUSE settings. It changes the package/settings/component identity namespace, type names and menu labels so the two installations coexist. All thirty released monitor queries and thresholds are unchanged. A copy of the matching Open Telemetry 0.1.4 companion supplies the inherited fields, trace bindings, service-instance/pod relations and four native monitors. Companion-only guards handle absent namespace/cluster attributes seen in this demo.

Four GPU node copies use actual captured node metadata and live DCGM refreshes. They depend on their actual Kubernetes nodes for underlying health. The legacy `properties.sts_host` value is carried through a comparison-only tag because [native mapping output](https://documentation.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/otelmappings/schemas-ref.html) does not expose arbitrary component properties. Only that interpolation is adapted: CPU and memory PromQL render identically to the release for all four actual hosts. Metadata is a capture from this demo, not a continuous Kubernetes synchronization; rebuild the comparison after a hardware/OS identity change.

The comparison has 35 monitors in total: 30 released SUSE checks, four copied OTel checks and one node-health bridge. These adapter checks are not counted as extra released product coverage. Normal SUSE AI and native OTel lists exclude the duplicate comparison service identities. Kubernetes namespace/cluster links and observed-node health references remain read-only links to the real infrastructure.

The full Kubernetes StackPack is not duplicated. Comparison pod details expose an **Observed pod** link to the real workload for its complete Kubernetes health, fields and configuration, using the captured native pod icon. A thin or UNKNOWN comparison pod is an isolation-context limitation, not evidence that the published SUSE AI release lacked Kubernetes integration.

Reproduction uses `task demo-comparison-build` with an explicit source ref, extracted OTel companion directory, topology snapshot and output directory, followed by `task demo-deploy DEMO_PACK_NAME=suse-ai-v300 DEMO_SOURCE=...` with the explicit demo URL/token/state directory. Use the same deployment state directory for both names so every upload receives a globally fresh development version. The comparison builder requires PyYAML, included in `tests/suse-ai/requirements.txt`.

## Evidence and validation

Private evidence is under `/home/thbertoldi/suse/qa/demo-release-comparison-20261109-us_4fm7v/`. `baseline/` contains before snapshots; `sources/` contains the verified release sources. `ux/monitor-audit/REVIEW.md` records the independent health audit; `ux/before-icons/`, `ux/after-icons/` and `ux/final/` contain actual UI captures. The intermediate icon contrast finding is retained rather than replacing its evidence.

The initial `.993` native suite ran 110 tests with 18 opt-in live tests skipped and no failures; the release/deployment suite passed 26, and three additional comparison-isolation tests passed. Actual CEL tests verified disjoint primary/comparison identities and missing optional metadata. That development package validated 143 nodes; removing eleven generic icon overrides reduces `.997` to 132. The invalid-CEL negative control was rejected. No Groovy source changed.

A known topology-mapping cache refresh gap initially delayed comparison discovery. Recreating only the demo backend Collector pod refreshed observations; its StatefulSet specification compared equal before/after. Application deployments and their data were not changed.

Final UI acceptance confirms populated tables on both sides, disjoint AI component IDs, working isolated service/model/agent/pod links, and compact readable product icons on light and dark surfaces. The comparison GPU table returns 24 finite metric queries, including all eight host CPU/memory queries. The observed-pod link resolves to the real native Kubernetes pod and its actual health. The final comparison package validates 131 nodes. All 190 development package files match the current source except the intentional development version in the manifest.

All 68 captured monitor runtime statuses (33 development, 35 comparison) have no evaluation errors or unmapped queries. The final comparison update changes only its pod icon and source-link label; its monitor definitions are unchanged. All 21 observed development mappings and all 31 observed comparison mappings return no mapping errors. Nine comparison mappings have no matching observations and return 404 status, rather than an evaluation error. Three earlier companion missing-attribute errors aged out after the guarded definitions and Collector refresh; their original evidence is retained.

Final `sts topology-sync list` and `describe` show both synchronizations Running. Kubernetes has zero errors. The built-in Agent retains 75 reported errors involving unresolved process/external-API targets, matching the baseline count. This is not a claim that the entire backend is error-free. Final comparison deployment evidence is under `/home/thbertoldi/suse/qa/demo-rebuild-20261109-d5tmgw2a/deploy-state/versions/3.0.0-dev.996/`.

The [independent UI review](/home/thbertoldi/suse/qa/demo-release-comparison-20261109-us_4fm7v/ux/final/REVIEW.md) includes paired screenshots. Useful captures are [both menus](/home/thbertoldi/suse/qa/demo-release-comparison-20261109-us_4fm7v/ux/final/menus.png), [current Ollama](/home/thbertoldi/suse/qa/demo-release-comparison-20261109-us_4fm7v/ux/final/current-ollama.png), [release GPU table](/home/thbertoldi/suse/qa/demo-release-comparison-20261109-us_4fm7v/ux/final/release-gpu-final.png), and [current GPU table](/home/thbertoldi/suse/qa/demo-release-comparison-20261109-us_4fm7v/ux/final/current-gpu-nodes.png).

For a direct comparison, open **SUSE AI → Overview / Models / GPUs** and **SUSE AI 3.0 release → Overview / Models / GPU infrastructure**. Open `ollama`, `qwen-small` and `demo-agent` from each menu to compare details and health. The complete source definitions and no-data cases are in the private adversarial reports; the public report deliberately contains no credentials or copied configuration secrets.
