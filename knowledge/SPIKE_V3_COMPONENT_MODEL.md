# Ollama component-model spike — 2026-11-05

**Recommendation: retain D1, with namespaced presentation field IDs. Do not start the complete D3 rollout until native domain/layer assignment is supported.** The overlay and separate inventory coexist with the Open Telemetry pages. D1b was therefore not needed or implemented. Separate service components would not resolve the independent S2 schema limitation.

This experiment implements only Ollama plus physical GPU discovery. The release manifest remains **3.0.0**; functional release settings are unchanged. Prototype sources, build tasks, icon drafts and install-copy drafts are under [experiments/component-model](../experiments/component-model/README.md).

| Spike | Result | Evidence and limits |
| --- | --- | --- |
| S1: presentation overlay | **Pass** | Native Services metadata identical; Ollama keeps the native icon, fields, trace bindings and layout, with the requested AI additions. Separate Inference servers page lists Ollama and three available models. |
| S2: domain and layers | **Blocked** | Classic settings can create SUSE AI and eight layers, but native v2 cannot package them and native mapping output drops domain/layer keys. Components remain in the defaults. |
| S3: GPU devices | **Pass on this demo** | Four physical GPUs, four `runs on` node relations and one `allocated to` Ollama pod relation from actual DCGM telemetry. No Collector change needed. MIG/shared GPU cases remain untested. |
| S4: operator monitor | **Pass for binding/rendering** | One added monitor evaluates CLEAR on the native Ollama service; named check and four-part remediation with a component link. A forced failing observation and missing-data alert were not tested. |
| S5: lifecycle | **Qualified** | Instance, native service and all 67 existing monitor IDs survive. Prerelease ordering requires downgrade into the spike and overwrite-upgrade back; this does not prove a forward upgrade from 3.0.1 into a lower version. Removal/re-addition exposed a mapping refresh gap. |

## Scope, baseline and local evidence

Tested on SUSE Observability **2.11.1**, Open Telemetry StackPack **0.1.4**, downstream cluster `suse-ai`, through explicit localhost port-forwards and the provided demo CLI wrapper. No SA/default-context operation was performed. Browser captures used Chromium with the authorized demo service-token header; responses and screens were real, with no mocked telemetry or API responses.

All evidence is local under **`/home/thbertoldi/suse/qa/component-model-spike-20261105/`**, referred to as `E` below. Links to captures intentionally require that local checkout; they are not GitHub-hosted assets. Existing `knowledge/evidence/` files were removed from the Git index and ignored, while retaining their local copies. Raw captures, credentials, configuration backups and archives are not part of this commit.

Before mutation, snapshots covered the installed instance/catalog, settings, monitor IDs, component/relation mappings, synchronization list and every description, topology, runtime/DCGM metrics, all 45 downstream workload specs and Collector ConfigMaps. `suse-ai-before.sty` is the classic export, not a complete native presentation backup: `/api/presentations` and the individual presentation export endpoint returned HTTP 500, “Not implemented in ComponentPresentationApiRoute”. The original archive was reconstructed from commit `422e9c1`; its SHA-256 is **`40e10e4478d52ecae08b06344540a75f92729472fa94c1f1f13c2cc6a33bace8`**, exactly matching the recorded original 3.0.1 upload. Resolved component and overview API responses provide the presentation baseline.

There are three deliberately distinguished stages:

1. **Before:** originally installed 3.0.1, including its SUSE AI Ollama presentation takeover.
2. **Control:** `3.0.0-spike.1`, excluding native Ollama services/instances from our existing presentations. Native component identity and topology mappings remain. This establishes the genuine Open Telemetry component layout to preserve.
3. **After:** `3.0.0-spike.6`, clean overlay at specificity 1, separate AI inventory, monitor and GPU components.

| Page | Originally installed | Native control baseline | Final overlay |
| --- | --- | --- | --- |
| Open Telemetry → Services | [Before screenshot](/home/thbertoldi/suse/qa/component-model-spike-20261105/otel-services-before.png) | [Control screenshot](/home/thbertoldi/suse/qa/component-model-spike-20261105/otel-services-control.png) | [After screenshot](/home/thbertoldi/suse/qa/component-model-spike-20261105/otel-services-after.png) |
| Native Ollama component | [Before screenshot](/home/thbertoldi/suse/qa/component-model-spike-20261105/ollama-before.png) | [Control screenshot](/home/thbertoldi/suse/qa/component-model-spike-20261105/ollama-control.png) | [After screenshot](/home/thbertoldi/suse/qa/component-model-spike-20261105/ollama-after.png) |

Other captures: [Inference servers](/home/thbertoldi/suse/qa/component-model-spike-20261105/inference-after.png), [Models](/home/thbertoldi/suse/qa/component-model-spike-20261105/models-after.png), [served-model navigation](/home/thbertoldi/suse/qa/component-model-spike-20261105/served-models-click.png), [model deep link](/home/thbertoldi/suse/qa/component-model-spike-20261105/model-saved-link.png), [GPUs](/home/thbertoldi/suse/qa/component-model-spike-20261105/gpus-after.png), [allocated GPU detail](/home/thbertoldi/suse/qa/component-model-spike-20261105/gpu-device-details.png), [monitor panel](/home/thbertoldi/suse/qa/component-model-spike-20261105/monitor-panel.png).

## S1: observed presentation composition

The exact installed Open Telemetry 0.1.4 source is available at commit `df0358f` in the local `~/suse/contrib-stackpacks` repository. Its service presentation has specificity **10**, and its common component presentation **2**. The final SUSE AI overlay uses **1**. It contributes metrics, one uniquely identified highlight field and a served-model related-resource entry. It has no presentation icon, overview or name override. The settings node's administrative `name` is not a component display-name override.

The separate overview binds `otel service` plus all three SUSE labels: `stackpack:suse-ai`, `suse.ai.category:inference-engine` and `suse.ai.product:ollama`. Its six columns are Health, Name, AI product, Available models, Loaded model copies and Cluster. It shows one Ollama row, three available models and two loaded copies at capture time. Selecting Ollama reaches the existing native service; selecting Served models opens a scoped list of `gemma:2b`, `llama3.2:latest` and `nomic-embed-text:latest`. Selecting the latter model links was also exercised in the browser.

The native Services columns remain **Health, Service, OTel Namespace, Kubernetes Cluster, Kubernetes Namespace, Span error %, Span duration, Span rate, Language**. Complete overview metadata compares equal, with canonical SHA-256 **`d73a05144e4503e1f7092e024840840c21b041e138a78874bce581ee27f2d864`**. Component identity stays `21793676483063`, with URN `urn:opentelemetry:namespace/suse-private-ai:service/ollama`.

Field-by-field observations below are verified for this backend and these probes. They are not a general specification of every merge conflict.

| Field or collection | Verified observation | Consequence |
| --- | --- | --- |
| `presentation.icon` | With the overlay omitting it, the resolved icon remains `/api/stackpack/open-telemetry/icons/0.1.4/services.svg`. | Omit role/vendor icons on the native service overlay. |
| Component `name`, `typeName`, summary | Ollama's name/type and resolved summary match the control. No display-name override was supplied. | Keep native naming. Conflicting name/title precedence was not tested. |
| `highlight.fields`, distinct IDs | All seven native field objects remain identical and in their original relative order; `suse_ai_spike_product` is added. | Fields compose; use a SUSE-specific ID. |
| `highlight.fields`, duplicate ID | A probe named `namespace` replaced the native link with the probe's title/projection/order, both at specificity 10 and at **−10**, below the native presentation. | Low specificity alone does **not** protect native highlight fields from ID collisions here. Do not infer a general tie-break rule from these runs. |
| `highlight.relatedResources` | All original entries survive unchanged; the uniquely identified Served models entry is added. | Add distinct resource IDs; duplicate-resource-ID conflicts were not tested. |
| `highlightMetrics` | Native Traces and Service sections and their metrics remain identical; the Ollama runtime section is added ahead of them. | Unique section/metric IDs preserve native content. Duplicate section/metric merge rules were not tested. |
| `overview.columns`, sort and metadata | The Open Telemetry view's entire metadata stays identical while our explicit view resolves its own six columns. | An overview bound to the same service can coexist as a separate list. It does not replace the native Services columns in this test. |
| `overview.mainMenu` | The new Inference servers entry opens our explicit presentation route; the OTel Services route remains usable. | Separate navigation is viable; final menu ordering for all products remains D4 work. |
| `boundTraces` | Native trace filter is identical. | Traces remain on the merged service. |
| `events` | Resolved events configuration is identical. | Existing event scope is preserved. Live event counts naturally change. |
| `links`, `actions`, `provisioning` | Resolved values equal the control when omitted by the overlay. | Omission preserves these contributions in this test. Conflicting values were not tested. |

The exact comparison is [s1-comparison.json](/home/thbertoldi/suse/qa/component-model-spike-20261105/s1-comparison.json). Inputs are `ollama-detail-control.json`, `ollama-api-after.json`, the control overview response in `otel-services-control.json`, and `otel-api-after.json`. Collision evidence is in `ollama-detail-spike3.json`, `ollama-detail-spike4-later.json` and `ollama-spike4.png`; original 0.1.4 sources are `otel014-*.sty`.

“Unchanged” applies to native layout/configuration, icon and columns, with the explicitly requested AI highlights/metrics added. Screenshots are not pixel-identical: live metrics, health sorting, time ranges, model data and the added monitor change. The native content is retained; the whole final page cannot be byte-identical while adding charts. The official [presentation schema](https://documentation.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/presentation/schemas-ref.html) describes the fields; the observations above, including the collision result, come from this live comparison.

## S2: domain/layer assignment is not supported by this native path

The desired order was staged as SUSE AI → AI Applications, AI Agents, AI Gateways, MCP Tools, Inference Servers, Models, Data Services, GPUs. The isolated [classic settings diagnostic](../experiments/component-model/graph-settings/layers.sty) creates the domain and eight ordered layers. It is intentionally outside native package settings.

The pinned validator rejects `_type: Domain` and lists supported native node types without either Domain or Layer (`overlay-validation.log`). Passing `domainName`, `domainIdentifier`, `layerName` and `layerIdentifier` in a native component mapping does not establish membership: the server-normalized mapping descriptions omit them. Even while the classic domain and layers exist, native Ollama, all three models and all four GPUs still return `urn:system:default:domain:selected` and `urn:system:default:layer:selected` in topology snapshots. This agrees with the output fields in the documented [native mapping schema](https://documentation.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/otelmappings/schemas-ref.html).

Evidence: `domains-s2.json`, `layers-s2.json`, `s2-topology-with-settings.json`, `normalized-ollama-layer-6.yaml`, `normalized-gpu-6.yaml`. The classic settings were reapplied after spike.6 so the result cannot be explained merely by an earlier upgrade pruning them. Returning to the original release subsequently removes these unowned-by-the-package additions.

The prototype retains these unsupported output keys solely to reproduce S2. They must be removed from a production candidate unless platform support is established. Resolve native settings packaging **and** component assignment with the platform team, or validate a supported alternative provider. Creating separate D1b services still goes through the same unsupported output contract and is not a demonstrated solution.

## S3: real DCGM GPU identity and allocation

The demo runs Collector **0.164.1**, image `ghcr.io/suse/suse-ai-opentelemetry-collector:0.164.1` at digest `sha256:7bb0b0a6128fdc2659c72acf7b26c9acac56b51685610806ef3b8683cb2c7744`, on Collector chart 0.178.2. The Agent chart is **1.7.19**, application **3.78.2**. Actual metric labels and the running Collector configuration were inspected; no Collector configuration was changed.

| Observed data | Use |
| --- | --- |
| `UUID`, `gpu`, `modelName`, `pci_bus_id`, `Hostname` | Device identity and descriptive labels. All four devices identify as Tesla T4. |
| Resource `k8s.cluster.name`, `k8s.node.name` (query labels `k8s_cluster_name`, `k8s_node_name`) | Cluster-scoped identity and node target. |
| Datapoint `pod_namespace`, `pod_name`, `container_name` | Workload allocation, where populated. The Collector's DCGM scrape copies source `namespace`, `pod`, `container` to these names using metric relabeling. |
| Exporter resource pod/namespace | Identify the DCGM exporter in `gpu-operator`; these are **not** workload allocation labels. |

GPU identity is `urn:suse-ai:/<cluster>:gpu/<UUID>`, type `genai gpu`. A `runs on` relation targets `urn:kubernetes:/<cluster>:node/<node>`. An `allocated to` relation requires nonempty workload namespace and pod and targets `urn:kubernetes:/<cluster>:<namespace>:pod/<pod>`. Missing allocation labels produce no guessed pod relation. The device and relation expiry is five minutes.

| UUID | Node | Allocation observed |
| --- | --- | --- |
| GPU-1559009e-a472-c14d-408d-1a4c169bdc50 | suse-ai | None |
| GPU-b1415cd1-c45d-3298-7e59-93cfa98bd492 | suse-ai-wkrgpu1 | None |
| GPU-d9d10a91-13c7-7a00-fc65-b518d69ee917 | suse-ai-wkrgpu2 | None |
| GPU-3b2d4643-cd4d-5898-4619-ab5eec44a1fb | suse-ai-wkrgpu3 | `suse-private-ai/ollama-6b97654c87-7vs6d` during the spike |

Evidence: `topology-spike6.json`, `audit/component-mapping-status-after.json`, `audit/relation-mapping-status-after.json`, `DCGM_FI_DEV_GPU_UTIL-final.json`, and `dcgm-scrape-reviewed.json`. The final mapping status reports four devices and no mapping errors; actual topology contains the four node edges and one workload edge. The GPU component UI shows one node and one allocated pod.

**Collector changes needed for this demo: none.** For other supported profiles, retain UUID and workload allocation labels, normalize cluster/node into resources, and preserve the workload/exporter distinction. These are compatibility requirements, not a proposed change to the tested Collector. Validate MIG identity, time slicing, multiple pod allocations and stale-allocation expiry before generalizing beyond physical GPUs in this demo.

## S4: one operator monitor

[The monitor](../experiments/component-model/settings/ollama-monitor.sty) uses the latest per-instance `ollama_api_up` values, takes the minimum for the merged service and marks values below 1 DEVIATING. Its check title is **“Inference server ollama: model inventory unavailable”**. The result identifies the existing native service, not a duplicate AI node. This measures runtime inventory visibility, not inference request success.

[Remediation](../experiments/component-model/includes/ollama-api.md.hbs) has Check first / Likely causes / Fix / Verify and uses `componentUrnForUrl` to link to the native component. `monitor-after.json` records a real run: CLEAR, no errors, correct service URN and correctly encoded template data. The browser monitor panel displays the check beside the original endpoint check. No missing-data behavior or forced production failure was asserted.

A useful packaging failure was caught: spike.2 passed the offline validator but installation rejected inline Handlebars in native settings. Moving the hint into `!include` allowed the backend to load it. `deploy-spike2.log` records the failure; later installations and the live monitor run verify the correction.

## S5: lifecycle, identities and links

Only fresh versions **3.0.0-spike.1–6** were uploaded, once each. These numbers remain consumed even though their catalog entries were deleted.

| Version | Purpose / outcome |
| --- | --- |
| spike.1 | Native control, installed successfully. |
| spike.2 | Inline Handlebars rejected during preprocessing; restored existing 3.0.1 before continuing. |
| spike.3 | Overlay and field-collision probe at specificity 10; models, GPU relations and monitor working. |
| spike.4 | Collision probe at −10 still replaced native `namespace`. |
| spike.5 | Clean specificity-1 overlay passed native layout checks; repeated removal/re-addition left GPU mapping status without observations despite current DCGM metrics. |
| spike.6 | Fresh experimental mapping setting identifiers restored four devices/five edges without restarting a backend; final evidence captured. |

Entry from installed 3.0.1 used `stackpack downgrade --stackpack-version 3.0.0-spike.N`; SemVer places these prereleases below the installed release. Return used `stackpack upgrade --unlocked-strategy overwrite`. No delete/recreate of the SUSE AI instance was used. This tests both transitions while preserving an instance, but not the normal release installer's forward-upgrade policy into a lower version.

| Object | Observed behavior |
| --- | --- |
| SUSE AI instance | ID **197048877569388** retained across all successful transitions and restoration. |
| Native Ollama service | ID **21793676483063** and service URN retained; native links and traces continue to resolve. |
| Existing monitors | All **67** original monitor IDs and definitions retained. Overwrite recreates nested argument/metric IDs and updates timestamps for 30 SUSE AI monitor records; those generated IDs are not stable. spike.6 adds one monitor, ID **97531492256987**; restoration removes the experimental monitor. |
| Served models | Initial baseline had none because the original exporter lacks inventory metrics. During populated spike.3–6, IDs remain gemma **9866539968813**, llama3.2 **144934475407127**, nomic **180328474005240**. No claim of continuity with already expired models is made. |
| GPU devices | URNs stay stable. Numeric IDs change after mapping removal/expiry and re-creation, so new settings IDs are only a test workaround, not a release migration strategy. |
| Ollama pod / service instance | Temporary exporter deployment causes a rollout and new pod UID, hence new OTel instance identity. This is a workload rollout effect, not loss of the merged service from a StackPack transition. |
| Saved component links | The native service URN and active served-model URNs resolve in actual browser navigation, including `:latest` names. Model links cease representing current inventory after source telemetry expires. |
| Menu links | Existing views remain present; old inference view excludes Ollama during the isolated experiment, and the new explicit Inference servers route lists it. A full menu migration needs a compatibility decision. |
| Historical temporary checks | Some check-history requests reference already removed spike monitor IDs and return 400. These are not evidence of preserved temporary-monitor history. A baseline perspective endpoint also returned 404. No claim of a browser session with zero failed requests is made. |

The mapping refresh gap is reproducible across remove/re-add cycles, but its internal cause was not isolated. spike.6 used `-6` on new mapping **setting** identifiers, while preserving component URNs. Normal production mappings should update in place with stable identifiers; deletion/reinstallation and cached observations need a dedicated regression test before the complete redesign.

The original demo exporter image, also tagged 3.0.0, lacks `ollama_model_info`. To test real inventory without publishing an image, the repository's inventory-capable exporter file was temporarily mounted read-only via ConfigMap into the existing sidecar. No Collector change, synthetic telemetry or explicit model mutation was used. The existing Ollama postStart hook runs its configured model initialization on rollout. Restoration replaces the entire original Deployment spec, removes the temporary ConfigMap and waits for rollout; ephemeral pod IDs cannot be restored.

## D5/D7 drafts and resource rendering

Original SVG sources: [inference server](../experiments/component-model/icons/inference-server.svg), [model](../experiments/component-model/icons/served-model.svg), [GPU](../experiments/component-model/icons/gpu-device.svg), with [local preview](/home/thbertoldi/suse/qa/component-model-spike-20261105/icons-preview.png). All use a 40×40 grid, 2-unit outline, `#30BA78` glyph and `#E4F5EB` tile. No stock PNG or vendor artwork was reused. Provenance is recorded in [LICENSES.md](../stackpack/suse-ai/icons/LICENSES.md) and the linked draft inventory. They are review drafts; obtaining an existing SUSE brand library and its licence remains a full-redesign task. No external message was sent to brand/design.

Install-copy drafts: [overview](../experiments/component-model/resources/overview.md), [detailed overview](../experiments/component-model/resources/detailed-overview.md), [configuration](../experiments/component-model/resources/configuration.md). They provide the value statement/topology chain, data sources and concrete signals, contributed concepts, prerequisites, three-step setup and monitoring-guide link. Domain/layer wording describes the intended redesign and is gated on S2. Tested versions are identified rather than invented minimum requirements.

Screenshot resource test: `![...](spike-control.png)` resolved to the UI origin root and failed to load. The explicit versioned URL `/api/stackpack/suse-ai/resources/3.0.0-spike.6/spike-control.png` loaded with natural dimensions 1840×1050. Evidence: `install-after.json` and [install capture](/home/thbertoldi/suse/qa/component-model-spike-20261105/install-after.png). The overview is height-collapsed by the UI. An expanded-page capture attempt was blocked by the introductory modal, so full expanded rendering is not claimed. Final screenshot authoring must use version-aware resource links and verify the expanded page. The source text drafts contain no screenshot probe.

## Verification and restoration

The pinned native validator accepted **104** settings nodes in spike.6, including after the Taskfile path-quoting correction. Four executed CEL tests cover GPU identity, relation identity agreement, workload attribution and missing labels. All **15** release/package/installer regressions passed. Python syntax, three SVG documents and `git diff --check` also passed. The final local 3.0.0 archive has SHA-256 `3e379ac18996dab02201f85d69c5ebe967ef0af81ddc422cd78a5ec7ee4c6c95`; its only release-package addition is the icon provenance note. No Go or Groovy source changed, and no ComponentType `iconbase64` field was modified.

Both `sts topology-sync list` and `describe` were captured before and during the experiment. Agent and Kubernetes - suse-ai remained Running, with pre-existing cumulative error counts **79/34** and **ten active error details each**, unchanged through the final spike. The exit criterion “no topology-sync errors” therefore cannot literally be met on this baseline; the verified result is no added errors. Errors were not cleared. Native mapping statuses are captured separately: absent observations for unrelated integrations are distinguished from mapping error details.

The final readback at **20:22 UTC** confirms restoration. [The comparison](/home/thbertoldi/suse/qa/component-model-spike-20261105/restore-comparison-wrapup.json) and `audit/*-wrapup.json` record:

| Restored state | Result |
| --- | --- |
| SUSE AI instance | Original ID `197048877569388`, original config, 3.0.1, INSTALLED. |
| Catalog and mappings | Exact original catalog (2.0.0, 3.0.0, 3.0.1); all six test versions deleted; original 20 component and 14 relation mapping entries match. |
| Settings | All 31 classic SUSE AI definitions match; original three domains and 17 layers match. Experimental SUSE AI domain/layers are absent. |
| Monitors | All 67 original IDs and definitions match; the added monitor is absent. Generated nested IDs/timestamps changed as described in S5. |
| Workloads and Collector | All 45 downstream workload specs and Collector ConfigMap data match; Ollama rollout completed; temporary ConfigMap removed. Restored pod UID is `b9748bcd-2065-4c4f-a6d9-74a5b1a5b4d0`. |
| Topology and telemetry | Ollama service remains `21793676483063` and CLEAR; original exporter reports `ollama_api_up = 1`. Test GPU components are absent; all three served models aged out, restoring the initial empty inventory. |
| Presentations | Original Ollama icon, highlight configuration, related resources, metric sections, trace bindings and native Services metadata match. The original release's takeover behavior is restored, as requested. |
| Synchronizations | Both Running; error counts 79/34 and all active error details match the baseline. |

All 33 historical evidence files removed from Git tracking were checked against their original Git blobs and remain byte-identical locally. Evidence remains local and the repository stays on `feat/ollama-model-inventory-3.0.1`. No push, tag or remote PR update was performed; a later authorized push is needed to apply the evidence removal to GitHub's PR diff.

## Task breakdown for the complete redesign

| Order | Work | Completion evidence |
| --- | --- | --- |
| 1 | Resolve S2 native Domain/Layer packaging and assignment with the platform contract, or validate a supported provider. | Fresh native service/model/GPU components appear in SUSE AI and the intended layers, survive an update, and cleanly restore. Remove silently ignored probe keys. |
| 2 | Convert the remaining role/product presentations to D1 overlays. Audit every field/resource/section/metric ID for collisions. | Native OTel service and instance screenshots/API schemas remain intact for each supported product; trace/log bindings and native monitor links still work. |
| 3 | Generalize owned concepts and typed relations: served models, model usage, agents, tools, dependencies and physical GPUs. | Stable URNs across replicas/restarts; no merge by model name alone; tested expiry, allocation changes, cluster separation, MIG and sharing policy. |
| 4 | Implement D4's complete ordered menu and label-scoped list pages. Decide redirects/retention for existing view identifiers. | Every entry has a clear scope, valid empty/populated states, no overlap surprises, and tested old/new bookmarks. |
| 5 | Obtain the SUSE icon library/licences, review the three drafts, complete the family and replace legacy stock PNG usage. | Consistent grid/stroke/palette and source/licence for every shipped asset; no ComponentType icon-field edits. |
| 6 | Extend D6 monitor coverage with component-naming titles, four-part hints and tested links. Add explicit missing-data policy where appropriate. | Live good/failing/recovery cases, replica aggregation, no-data cases, custom override behavior and original monitor identity/history checked. |
| 7 | Finalize D7 copy and screenshot resources after S2 and menu behavior are settled. Pin the inventory exporter and supported Collector/Agent combinations. | Fresh install/update pages reviewed in-browser, versioned images resolve, quick start followed successfully and published compatibility requirements verified. |
| 8 | Run a release migration rehearsal using the intended 3.0.0 regeneration/cleanup policy on a disposable demo. Investigate remove/re-add refresh and temporary monitor-history behavior. | Forward upgrade from an appropriate older version, reinstall, rollback, identity/link/customization checks, topology/mapping status and a complete restore. |
| 9 | Regenerate release artifacts and prepare release notes/monitoring-guide changes. | Deterministic package, native validator plus negative control, targeted regression suite and approved screenshots. Publishing, tags, pushes and PR updates require the user's separate confirmation. |

References consulted: [design decisions D1–D7](DESIGN_V3_COMPONENT_MODEL.md), local AI Factory `FINDINGS.md` and `image (30).png` / `image (31).png`, and the SUSE Virtualization StackPack's overlays, component/relation mappings and install resources. The live results above determine the recommendation; visual resemblance alone does not establish native API support.
