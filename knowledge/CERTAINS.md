# Verified Facts - GenAI Observability StackPack

## 1. Icon Validation
*   **Fact**: `ComponentType` and `ViewType` icons in STY files must be valid base64 strings.
*   **Fact**: PNG format with the `data:image/png;base64,` prefix is reliably accepted by the StackState backend. 
*   **Fact**: SVG format requires the `data:image/svg+xml;base64,` prefix.
*   **Fact**: Large base64 icon strings in `products.sty` must be single-line strings. Multiline base64 strings without proper YAML folding (like `>`) can cause validation failures like `iconbase64: Must be a valid icon.`.

## 2. Provisioning Constraints
*   **Fact**: `importSnapshot` using an empty node list (`nodes: []`) is NOT allowed and will result in a provisioning error.
*   **Fact**: If any node in an imported snapshot is missing a required field (based on its `_type` schema), the entire transaction is rolled back.
*   **Fact**: `Sync` nodes REQUIRE the `componentActions` field to be present, even if empty (`componentActions: []`).
*   **Fact**: `Sync` nodes only support `SyncActionCreateComponent` and `SyncActionCreateOnMerge` for component-related actions. `SyncActionCreateRelation` is NOT supported in `componentActions`.
*   **Fact**: Every node in the `nodes:` list must have a unique `id` (negative integer) and a unique `identifier` (URN). Duplicate IDs or identifiers across different STY files will cause `NamespaceSnapshotError`.

## 3. Handlebars Path Resolution
*   **Fact**: The `include` helper resolves paths starting from the `provisioning/` folder within the ZIP.
*   **Fact**: Double prefixes (e.g., `provisioning/provisioning/...`) cause `NoSuchFileException`.

## 4. Component Schema
*   **Fact**: Modern StackState schemas for `ComponentType` require the `externalComponent` field.
*   **Fact**: `QueryView` nodes require a `queryVersion` (e.g., `"0.0.1"`) to be properly indexed in some versions.
*   **Fact**: `ComponentType` nodes within `highlights` must have an `about` section defined, or they will fail with `Object is missing required member 'about'`.

## 5. Synchronization Logic
*   **Fact**: `IdExtractorFunction` returning `null` effectively filters out components from a synchronization.
*   **Fact**: `getOrCreate` helper provides robustness by falling back to auto-generated types if a specific URN is missing.
*   **Fact**: The `IdExtractorFunction` API signature is `Sts.createId(String externalId, Set<String> identifiers, String typeName)`.
*   **Fact**: Two distinct IdExtractorFunctions are used: `suse-ai-id-extractor.groovy` (adds `suse-ai:` prefix to OTel external IDs) and `suse-ai-product-id-extractor.groovy` (creates aggregated product IDs based on `suse.ai.component.name` and `suse.ai.component.type` tags).
*   **Fact**: Merging multiple STY files into a single `importSnapshot` master file prevents `NamespaceSnapshotException` caused by cross-file references.

## 6. Data Flow & Categorization
*   **Fact**: The SUSE AI synchronization uses a `suse-ai:` prefix for all components to ensure they remain separate from standard OTel components.
*   **Fact**: Multiplexed mapping is achieved by having two `Sync` nodes: one for Core mirroring (`suse-ai:<URN>`) and one for Product grouping (`suse-ai:product:<type>:<name>`).
*   **Fact**: The `component-mapping-function.groovy` adds a `suse.ai.category` label to all managed components (e.g., `suse.ai.category:application`, `suse.ai.category:vectordb`).
*   **Fact**: The `runs-relation-template.json.handlebars` file exists but is not referenced in the synchronization configuration; only `relation-template.json.handlebars` is used for all relation generation.
*   **Fact**: `QueryView` queries in `shared.sty` use `label = 'suse.ai.category:<category>'` instead of `type STARTSWITH` (which is unsupported in STQL) to correctly group specialized product types in the UI menus.

## 7. Product Component Types & Metric Bindings
*   **Fact**: Product-specific component types (e.g., inference-engine.vllm, vectordb.milvus) are defined in `products.sty`.
*   **Fact**: Metric bindings in `product-metrics.sty` use unique product-scoped identifiers (e.g., `urn:stackpack:suse-ai:shared:metric-binding:vllm:e2e-latency-avg`) to avoid global URN collisions.
*   **Fact**: All 170+ metric bindings in `product-metrics.sty` have unique negative IDs ranging from -500 downwards.
*   **Fact**: Top-level list items in included STY files MUST be indented with exactly 2 spaces (`  - _type: ...`).
*   **Fact**: The `genai-system-active` monitor uses the aligned URN pattern: `suse-ai:product:inference-engine:${gen_ai_system}`.

## 8. Taskfile Commands & Test Environment
*   **Fact**: The `stackpack-uninstall` task in `Taskfile.yaml` correctly uninstalls all instances with status 'INSTALLED' or 'ERROR'.
*   **Fact**: `integrations/otel-collector/otel-values.yaml` is the OTel collector Helm values file for the **test environment**. It contains hard-coded endpoints, credentials, and namespace references (`suse-private-ai`) specific to the test setup — not production-ready.
*   **Fact**: The test collector uses `K8S_CLUSTER_NAME` env var (default `"local"`) with `action: insert` so it only sets the cluster name if not already present from K8s metadata.

## 9. Documentation & Packaging

*   **Fact**: The StackPack's user‑facing markdown files (`overview.md`, `detailed‑overview.md`, `configuration.md`, `provisioning.md`, `waitingfordata.md`, `enabled.md`, `RELEASE.md`) reside in `stackpack/suse‑ai/resources/` and are referenced via `configurationUrls` in `stackpack.conf`.
*   **Fact**: The `configurationUrls` mapping follows the state machine: `NOT_INSTALLED` → `configuration.md`, `PROVISIONING` → `provisioning.md`, `WAITING_FOR_DATA` → `waitingfordata.md`, `INSTALLED` → `enabled.md`, `DEPROVISIONING` → `configuration.md`, `ERROR` → `configuration.md`.
*   **Fact**: The `overviewUrl`, `detailedOverviewUrl`, and `releaseNotes` fields in `stackpack.conf` resolve relative to the `resources/` directory inside the packaged `.sts` zip.
*   **Fact**: The `logoUrl` in `stackpack.conf` also resolves relative to `resources/`. The logo file MUST be placed in `stackpack/suse-ai/resources/logo.png`, not at the stackpack root.
*   **Fact**: The `stackpack-upload` task in `Taskfile.yaml` zips only `stackpack.conf`, `provisioning/`, and `resources/`. Files at the stackpack root (outside these directories) are NOT included in the `.sts` package.
*   **Fact**: Any markdown or asset files at the stackpack root (e.g., `stackpack/suse-ai/logo.png`, `stackpack/suse-ai/overview.md`) are unused duplicates — only the copies under `resources/` are packaged and served.

## 10. View Types
*   **Fact**: The GPU Nodes ViewType (`urn:stackpack:suse-ai:shared:view-type:gpu-nodes`) provides a detailed table with GPU-specific columns and metrics, extending the existing QueryView.
*   **Fact**: ViewType columns can reference metric bindings from both the SUSE AI stackpack (`urn:stackpack:suse-ai:shared:metric-binding:common:node-gpu-*`) and external stackpacks (`urn:stackpack:stackstate-k8s-agent-v2:shared:metric-binding:host-*`).
*   **Fact**: The `pathToIdentifier` for label‑based columns must point to a unique component identifier (e.g., `internalIP` for nodes) to correctly resolve component links.
*   **Fact**: ViewType files must be included in `suse-ai.sty` via `{{ include "templates/view-types/<file>.sty" "yaml" }}` to be provisioned. Creating the file alone is not sufficient.
*   **Fact**: QueryViews reference ViewTypes via `viewType: urn:stackpack:suse-ai:shared:view-type:<name>`. Without this reference, the QueryView uses the default table layout (no icon, no custom columns).
*   **Fact**: ViewType IDs use the -6000 range (e.g., -6001 for AI Applications, -6002 for All GenAI Components, up to -6009 for ML Registries).

## 11. Monitors
*   **Fact**: The OpenSearch cluster status monitors (red and yellow) are defined in `templates/monitors/opensearch/monitor.sty` with IDs -3002 and -3003.
*   **Fact**: The red monitor triggers a CRITICAL state when `elasticsearch_cluster_health{status="red"} > 0`, extracting component name via `label_replace`.
*   **Fact**: The yellow monitor triggers a DEVIATING state when `elasticsearch_cluster_health{status="yellow"} > 0`, extracting component name via `label_replace`.
*   **Fact**: Both monitors use `label_replace` to transform `elasticsearch_cluster_name` labels (e.g., "opensearch-cluster" → "opensearch") into `product_name` for URN matching.
*   **Fact**: Monitors attach to product components using URN pattern `suse-ai:product:search-engine:${product_name}` where `product_name` is derived from metric labels.
*   **Fact**: Remediation hints for OpenSearch monitors are located in `templates/monitors/opensearch/remediation-red.md.hbs` and `remediation-yellow.md.hbs` and are included using the Handlebars helper: `{{ include "templates/monitors/opensearch/remediation-red.md.hbs" "identity" }}`

## 12. Kubeflow Demo Verification (2026-08-11)
*   **Fact**: Ollama's `/api/embed` endpoint returned HTTP 200 with a 768-element vector only after `nomic-embed-text` was pulled into the live Ollama volume.
*   **Fact**: Milvus rejects collection names containing hyphens. The live RAG service created `demo_docs` with dimension 768 and seeded 8 documents.
*   **Fact**: The installed Kubeflow Model Registry AuthorizationPolicy accepts in-cluster requests carrying an `Authorization` header. Creating a model version through the v1alpha3 API requires `registeredModelId` in the payload. Final demo run `7fd9b56e-dbed-4196-b42c-67d085600e2a` registered `iris` model ID `1`, version `demo-20260811-e2e4` ID `19`, and artifact ID `5` with the exact KFP `minio://` model URI.
*   **Fact**: Direct calls to this multi-user KFP API require the `kubeflow-userid` header. KFP run `7fd9b56e-dbed-4196-b42c-67d085600e2a` (`iris-lifecycle-vzlcz`) completed the uncached prepare, train, quality-gate, register, deploy, and smoke-test lifecycle with state `Succeeded` using `kubeflow-user-example-com/default-editor`.
*   **Fact**: The demo KFP service account needs namespaced create/patch permission for `inferenceservices.serving.kserve.io` and create/get/patch for Secrets, ServiceAccounts, and Services. `helm/suse-ai-demo/templates/kubeflow-pipeline-rbac.yaml` grants exactly those verbs in the configured profile namespace.
*   **Fact**: The collector's product topology exporter does not infer product relations from `peer.service` alone. A topology-only OTTL transform can map KServe and Model Registry client-span attributes to synthetic `gen_ai.provider.name` values while leaving the normal sampled trace pipeline unchanged.
*   **Fact**: A specialized topology component must retain the collector-emitted external ID when emitted relations reference that ID directly. The normalized Model Registry URN can be retained as an additional identifier without breaking relation resolution.
*   **Fact**: StackPack `2.2.9` was uploaded and upgraded from `2.2.8` with `--unlocked-strategy overwrite`. `SUSE AI`, `SUSE AI Products`, and `SUSE AI Topology` were all `Running` with empty `errorDetails` in `sts topology-sync describe` after the upgrade.
*   **Fact**: A static Prometheus scrape for an absent Qdrant service emitted `up=0` telemetry and created a visible `vectordb.qdrant` product component. Removing that target, the absent OpenSearch receiver pipeline, and debug exporters from the cluster-specific collector values stopped their recurring scrape errors and debug log flood.
*   **Fact**: The customized Kubeflow Pipelines SVG in source and in the installed `workflow-engine.kubeflow-pipelines` ComponentType has SHA-256 `37a17f2e30fa14b7ba98f33d0ce32eb25d337755c3194b3f988d7decad62265c`; it is valid XML and decodes to 7,682 bytes. The Milvus SVG is also valid XML.
*   **Fact**: Final KServe revision `sklearn-iris-predictor-00004` loaded the exact artifact from run `7fd9b56e-dbed-4196-b42c-67d085600e2a`; `latestCreatedRevision` and `latestReadyRevision` were equal, and `suse-ai-sklearn-iris` had one endpoint selecting only that revision. The predictor ServiceAccount retained `suse-ai-registry` and the generated S3 credential Secret.
*   **Fact**: The KFP smoke step must compare `latestCreatedRevision` with `latestReadyRevision`. Using only `latestReadyRevision` selected revision `00002` while revision `00003` was still becoming ready; the regression is covered by `test_smoke_test_waits_for_latest_created_revision`.
*   **Fact**: Live VictoriaMetrics returned data for KFP API/gRPC, Argo workflow phases and queues, demo accuracy (`0.947368421052`), demo step durations, Model Registry HTTP status/validation, agent tools/iterations, RAG retrieval, and generated scenario metrics. The StackPack `2.2.9` lifecycle bindings use `last_over_time` plus `tlast_over_time` to retain the newest one-shot run within 24 hours; live queries returned all six latest step series and `inference_service="sklearn-iris", outcome="success", value=1` for the deployment smoke test.
*   **Fact**: The demo agent image `ghcr.io/thbertoldi/suse-ai-demo-agent-service:demo-20260811-numeric` is deployed by Helm revision `9`. Its prediction tool converts numeric strings to floats and a live string-valued call returned prediction `[2]`; invalid or non-positive values are rejected before KServe is called.
*   **Fact**: Final validation passed with 249/249 unique StackPack IDs, zero Groovy lint errors, Helm lint success, 20 Kubeflow tests, 9 agent tests, 3 traffic-generator tests, and Python bytecode compilation for the modified services.
*   **Fact**: A non-zero `errors` value in `sts topology-sync list` is cumulative and does not prove a current synchronization failure. For the final acceptance check, the three SUSE AI synchronization IDs were each `Running` and each `sts topology-sync describe` response had an empty `errorDetails` array; unrelated Agent and Open Telemetry synchronization errors were outside that validation scope.
*   **Fact**: Inspecting an installed setting with `sts settings describe` is necessary to distinguish a packaging or upgrade problem from a UI problem. After the 2.2.9 upgrade, the installed lifecycle MetricBindings contained the expected `last_over_time`/`tlast_over_time` expressions, and the installed Kubeflow Pipelines icon bytes matched the source hash exactly.
*   **Fact**: The final implementation snapshots are observability extension commit `64aadfa86d45171721f6c26b80dea5c1352701d5` on `feat/kubeflow-monitoring` and demo-app commit `75e862cb8962e776d2ada5be806f901c5a7ad0c9` on `feat/kubeflow-relations-demo`; both commits were verified to match their remote tracking branches.
