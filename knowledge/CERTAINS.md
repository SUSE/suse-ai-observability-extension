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
*   **Fact**: The vGPU container bindings preserve `(pod_namespace, pod_name, container_name, gpu, vgpu)` at node scope and `(container_name, gpu, vgpu)` at pod scope. The generated PR 51 merge against `main` has 255 unique StackPack IDs, zero Groovy lint errors, and both changed metric-binding STY files parse as YAML.

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
*   **Fact**: Validation StackPack `2.2.9` was uploaded and upgraded from validation build `2.2.8` with `--unlocked-strategy overwrite`. `SUSE AI`, `SUSE AI Products`, and `SUSE AI Topology` were all `Running` with empty `errorDetails` in `sts topology-sync describe` after the upgrade. These were temporary cluster-validation versions; the merge-target release metadata was subsequently normalized to `2.2.0` without another upload.
*   **Fact**: A static Prometheus scrape for an absent Qdrant service emitted `up=0` telemetry and created a visible `vectordb.qdrant` product component. Temporarily removing that target, the absent OpenSearch receiver pipeline, and debug exporters proved the source of the validation-cluster scrape errors and debug log flood, but those blocks were restored because the extension values must retain every supported integration even when a particular demo cluster does not deploy it.
*   **Fact**: The customized Kubeflow Pipelines SVG in source and in the installed `workflow-engine.kubeflow-pipelines` ComponentType has SHA-256 `37a17f2e30fa14b7ba98f33d0ce32eb25d337755c3194b3f988d7decad62265c`; it is valid XML and decodes to 7,682 bytes. The Milvus SVG is also valid XML.
*   **Fact**: Final KServe revision `sklearn-iris-predictor-00004` loaded the exact artifact from run `7fd9b56e-dbed-4196-b42c-67d085600e2a`; `latestCreatedRevision` and `latestReadyRevision` were equal, and `suse-ai-sklearn-iris` had one endpoint selecting only that revision. The predictor ServiceAccount retained `suse-ai-registry` and the generated S3 credential Secret.
*   **Fact**: The KFP smoke step must compare `latestCreatedRevision` with `latestReadyRevision`. Using only `latestReadyRevision` selected revision `00002` while revision `00003` was still becoming ready; the regression is covered by `test_smoke_test_waits_for_latest_created_revision`.
*   **Fact**: Live VictoriaMetrics returned data for KFP API/gRPC, Argo workflow phases and queues, demo accuracy (`0.947368421052`), demo step durations, Model Registry HTTP status/validation, agent tools/iterations, RAG retrieval, and generated scenario metrics. The validation build `2.2.9` lifecycle bindings use `last_over_time` plus `tlast_over_time` to retain the newest one-shot run within 24 hours; live queries returned all six latest step series and `inference_service="sklearn-iris", outcome="success", value=1` for the deployment smoke test.
*   **Fact**: The demo agent image `ghcr.io/thbertoldi/suse-ai-demo-agent-service:demo-20260811-numeric` is deployed by Helm revision `9`. Its prediction tool converts numeric strings to floats and a live string-valued call returned prediction `[2]`; invalid or non-positive values are rejected before KServe is called.
*   **Fact**: Final validation passed with 249/249 unique StackPack IDs, zero Groovy lint errors, Helm lint success, 20 Kubeflow tests, 9 agent tests, 3 traffic-generator tests, and Python bytecode compilation for the modified services.
*   **Fact**: A non-zero `errors` value in `sts topology-sync list` is cumulative and does not prove a current synchronization failure. For the final acceptance check, the three SUSE AI synchronization IDs were each `Running` and each `sts topology-sync describe` response had an empty `errorDetails` array; unrelated Agent and Open Telemetry synchronization errors were outside that validation scope.
*   **Fact**: Inspecting an installed setting with `sts settings describe` is necessary to distinguish a packaging or upgrade problem from a UI problem. After the validation build `2.2.9` upgrade, the installed lifecycle MetricBindings contained the expected `last_over_time`/`tlast_over_time` expressions, and the installed Kubeflow Pipelines icon bytes matched the source hash exactly.
*   **Fact**: The final implementation snapshots are observability extension commit `64aadfa86d45171721f6c26b80dea5c1352701d5` on `feat/kubeflow-monitoring` and demo-app commit `75e862cb8962e776d2ada5be806f901c5a7ad0c9` on `feat/kubeflow-relations-demo`; both commits were verified to match their remote tracking branches.

## 13. OpenTelemetry Collector Configuration Verification (2026-09-03)
*   **Fact**: The productized `opentelemetry-collector` chart `0.149.0` prepends its default `dp.apps.rancher.io` registry unless `image.registry` is explicitly empty. With `image.registry: ""` and the full GHCR path in `image.repository`, both the productized chart `0.149.0` and upstream chart `0.165.0` render `ghcr.io/suse/suse-ai-opentelemetry-collector:0.156.0`.
*   **Fact**: The chart's `kubernetesAttributes` preset prepends `k8sattributes` ahead of configured processors. Defining `k8s_attributes` explicitly and wiring it after `memory_limiter` keeps `memory_limiter` first in every rendered pipeline while retaining the preset's metadata, pod-label, OTel-annotation, and pod-association behavior.
*   **Fact**: With a `1Gi` container memory limit and `useGOMEMLIMIT: true`, both chart `0.149.0` and chart `0.165.0` render one `GOMEMLIMIT=819MiB` environment variable.
*   **Fact**: The PR 54 Helm-rendered configuration and Operator configuration both pass `validate` with `ghcr.io/suse/suse-ai-opentelemetry-collector:0.156.0`; the four-resource Operator manifest also passes strict kubeconform validation, including the `OpenTelemetryCollector` v1beta1 schema.

## 14. Container Release Verification (2026-08-20)

The first two entries preserve the historical build/push record. The 2026-09-09 recheck below verifies artifact contents and the registry digest, rather than independently reconstructing which commands originally built or pushed it.

*   **Fact**: Git tag `v2.2.0-rc0` at commit `510ceabdea69b8a01ecc0e3716b378cc766b3e17` was built through the Taskfile as the Linux/amd64 image `ghcr.io/thbertoldi/suse-ai-observability-extension-setup:2.2.0-rc0` and pushed successfully. GHCR resolves the published manifest to `sha256:2096051ea2ca18f436946f93f116fb19cb9d1cbcadf579e7577261e2a593b7f1`.
*   **Fact**: The published release-candidate image contains StackState CLI `3.3.8` and an intact `/mnt/suse-ai.sts` archive with StackPack version `2.2.0`. Source validation reported 249/249 unique StackPack IDs and zero Groovy lint errors.
*   **Fact**: On 2026-09-09, GHCR returned the same RC0 manifest digest. The locally cached RC0 image reported CLI `3.3.8`; its archive passed ZIP integrity checking, contained 249 unique numeric StackPack IDs, and all 100 packaged files matched `v2.2.0-rc0` byte-for-byte. The final `v2.2.0` tag has different `common-metrics.sty` and `gpu-metrics.sty` contents despite the same embedded `2.2.0` version. RC0 artifact validation therefore does not establish final-release equivalence.

## 15. Topology Exporter Compatibility (2026-09-03)
*   **Fact**: SUSE AI StackPack source tags `v2.0.0` and `v2.0.1` consume `sts_topo_suse-ai_local`; the checked `v2.1.0` and `v2.2.0` tags consume `sts_topo_suse-ai_collector`.
*   **Fact**: Collector `v0.149.0` exposes configurable `instance_type` and `instance_url` values, defaulting to `suse-ai` and `local`; pairing that exporter with SUSE AI StackPack `2.1.0` or `2.2.0` requires `instance_url: collector`. This is only the stream-identity requirement: `v0.149.0` does not expose the `cluster_name` or `retention` configuration keys used by newer exporter versions.
*   **Fact**: `K8S_CLUSTER_NAME` supplies the `k8s.cluster.name` resource identity and must match the Kubernetes StackPack cluster name, but it is not the SUSE AI topology stream identifier and must not be substituted for `instance_url`.
*   **Fact**: Collector `v0.149.0` clears accumulated components and relations when taking a snapshot. Commit `b0670b6` introduced retention across flushes, and the checked `v0.156.0` exporter defaults that retention to 15 minutes. Exporter retention is separate from the StackPack topology data source's `expireElementsAfter` setting.
*   **Fact**: At extension tag `v2.2.0` (`f444ae428d711ce76eb49f6be0be0ed5b93a2d74`), both Collector examples pin image `0.156.0`, omit `instance_url`, and set `cluster_name` separately; that Collector fixes the topology stream contract to `suse-ai`/`collector`. This records the extension's pin, not the latest Collector release.

## 16. Version 2.2.0 Review (2026-09-09)

Evidence, reproduction conditions, severity, and validation limits are recorded in [REVIEW_2.2.0.md](REVIEW_2.2.0.md).

*   **Fact**: `main` was fast-forwarded from `510ceab` to `f444ae4`, matching remote tag `v2.2.0`. Remote tag `v2.1.0` resolves to `5274216`. The `CERTAINS.md` conflict was between independent appended sections; upstream content and both local sections were preserved, with the local sections renumbered to 14 and 15.
*   **Fact**: `task stackpack-validate` passed with 255 unique numeric IDs and zero Groovy lint errors (27 warnings). The expanded master template contains 269 unique node identifiers. The upstream Helm chart `0.165.0` render and Operator Collector configuration both passed the pinned `0.156.0` image's `validate` command using placeholder environment values and a dummy ServiceAccount token file.
*   **Fact**: In a local comparison using the same Collector executable, the unchanged tail sampler rejected a 600-span ordinary HTTP trace in both versions. The `2.1.0` trace-export branches emitted zero spans; the added `2.2.0` `traces/kubeflow-relations` branch emitted all 600 spans.
*   **Fact**: Given GenAI metrics with `k8s.namespace.name=tenant-a` and no `service.namespace`, the application-inference pipeline preserved `tenant-a` in `2.1.0` and changed it to `suse-private-ai` in `2.2.0` with that `SUSE_AI_NAMESPACE` value.
*   **Fact**: Executing the `2.2.0` Groovy mapper with a Model Registry namespace label of `ml-platform` replaced it with `kubeflow`. The product ID extractor, when given the synthetic check's `ml-registry` tags, produced the canonical ML-registry identifier without the legacy inference-engine identifier referenced by all three Model Registry monitors.

*   **Fact**: With Collector `0.156.0`, an HTTP 200 response missing the configured `"items"` substring emitted `httpcheck.validation.failed=1` and no `httpcheck.validation.passed` sample. With only the failed signal present, the shipped invalid-response monitor expression returned an empty vector in a local VictoriaMetrics query.
*   **Fact**: In local query fixtures, the shipped KServe monitors returned a 90.91% reconcile error ratio and 120 seconds of unfinished work from an unrelated controller while the KServe series had zero errors and zero unfinished work. The new pod vGPU container binding returned 90% for a 10% pod when another namespace contained a same-named pod on the same node with a matching container/GPU/vGPU and 90% utilization.
*   **Fact**: Live synchronization could not be checked: `sts topology-sync list` and `sts topology-sync describe` failed to connect to the configured `localhost:8081` endpoint; the alternate `local` context at `127.0.0.1:8090` also refused connections. This review did not upload or deploy a StackPack.

## 17. Fix Verification with Temporary Version 2.2.10 (2026-09-09)

The following facts record validation of the corrected working tree using
temporary version metadata `2.2.10`, before the official `2.2.0` designation in
section 18. They do not describe an installed release.
Reproduction setup and validation boundaries are in [REGRESSION_TESTS.md](REGRESSION_TESTS.md).

*   **Fact**: `task version-up TARGET_VERSION=2.2.10` advanced `stackpack.conf` from `2.2.0` to `2.2.10`, above the recorded temporary validation versions `2.2.8` and `2.2.9`. Isolated Git fixtures verified default patch increments, explicit higher targets, and rejection of downgrades, invalid versions, and versions consumed by release/candidate tags.
*   **Fact**: `task stackpack-test` passed all 19 tests using the Collector executable extracted from image `0.156.0`, VictoriaMetrics `v1.151.0`, and the Groovy runtime bundled with `npm-groovy-lint@18.0.0`. The Helm example rendered with upstream chart `0.165.0`; both full Collector configs passed the pinned executable's `validate` command using placeholder credentials.
*   **Fact**: For both Collector examples, the runtime fixtures exported zero backend spans from a rejected 600-span ordinary trace and exactly one copy of each of three accepted Kubeflow fixture spans. KServe/Registry `peer.service` hints remained present. The actual topology exporter sent KFP-to-KServe and KFP-to-Registry relations to a local HTTP intake without adding synthetic GenAI provider attributes to the ordinary backend trace path.
*   **Fact**: Application-inference fixtures preserved `tenant-a` both with and without a conflicting logical `service.namespace`. Missing namespaces fell back to `service.namespace` or `SUSE_AI_NAMESPACE`. Both actual HTTP-check pipelines produced Model Registry resources with `k8s.namespace.name=ml-platform` when `KUBEFLOW_NAMESPACE=ml-platform`.
*   **Fact**: The Groovy fixtures preserved incoming namespace labels, including multiple namespaces, without inventing one when absent. Both canonical and legacy topology discovery paths retained their external IDs and exposed the canonical ML-registry identifier now targeted by all three Model Registry monitors. Unrelated Milvus topology remained unchanged.
*   **Fact**: Exact Model Registry monitor/chart queries evaluated correctly against sparse failed/passed samples through failure, recovery, and relapse; an independent healthy endpoint did not hide a failed endpoint. Availability queries followed changing HTTP-status label sets, and absent check samples yielded empty results.
*   **Fact**: KServe query fixtures excluded unrelated controller errors and lag, still returned a 50% error ratio and 90-second lag for actual KServe failures, retained two distinct named queues, and distinguished missing controller metrics from an idle observed controller.
*   **Fact**: GPU query fixtures selected the intended pod's value of 10 instead of same-named workloads' 90/99 values in another namespace/cluster. Node vGPU queries retained both namespaces from the selected cluster and excluded the other cluster. The framebuffer query returned bytes after multiplying MiB by `1048576`.
*   **Fact**: The topology data source is configured to expire elements after `300000` milliseconds without updates. All packaged metric-binding references resolve after correcting the Milvus request-success reference. All 25 component-type `iconbase64` fields match `HEAD` byte-for-byte.
*   **Fact**: `task stackpack-validate` passed with 255 unique numeric IDs and zero Groovy lint errors across five shipped scripts and one test fixture. The linter still reports 26 warnings in shipped scripts and four in the fixture. `git diff --check` passed, and there are no unmerged index entries.
*   **Fact**: `task stackpack-sync-status` attempted `sts topology-sync list` and `describe` for all three SUSE AI sync identifiers. Each request failed because `localhost:8081` refused the connection. No StackPack upload, upgrade, or Collector rollout was performed; live provisioning, monitor attachment, and upgrade behavior remain unverified.

## 18. Official Version 2.2.0 Designation (2026-09-10)

*   **Fact**: The user explicitly designated `2.2.0` as the official version for the corrected source and stated that they would recreate the tag. This supersedes the earlier proposal to release these fixes as `2.2.10`.
*   **Fact**: `stackpack.conf` now declares `version = "2.2.0"`. The release notes combine the fixes and Kubeflow additions under a single `Version 2.2.0` entry, and the current Kubeflow guide uses `2.2.0`.
*   **Fact**: The original review remains tied to commit `f444ae428d711ce76eb49f6be0be0ed5b93a2d74`, and section 17 preserves the validation history under its temporary metadata. This metadata update did not recreate or push a Git tag.

## 19. Commit and Pull Request Delivery (2026-09-10)

*   **Fact**: The user explicitly requires repository work to include a commit and an opened pull request before the task is considered complete. This delivery requirement is recorded in `AGENTS.md` section 6.
*   **Fact**: A fresh `git fetch --no-tags origin main` returned `f444ae428d711ce76eb49f6be0be0ed5b93a2d74`, matching the base used to implement and validate the fixes. The official StackPack version remains `2.2.0`.
*   **Fact**: The fixes, regression tests, documentation, and delivery rule were committed as `387486dd93c34f6bd67992bb5bdce4eb1ab6ad6f` and pushed to `origin/fix/2.2.0-regressions`. [Pull request #59](https://github.com/SUSE/suse-ai-observability-extension/pull/59) is open against `main`; GitHub reported it mergeable after creation.
*   **Fact**: The pre-PR `task stackpack-sync-status` retry again received connection-refused errors from `localhost:8081` for the list request and all three describe requests. Live deployment verification remains outstanding.

## 20. Ollama SUSE Image Validation and PR Delivery (2026-10-28)

*   **Fact**: Commit `23f7929` adds the SUSE BCI Python 3.13 exporter image, ConfigMap-free sidecar migration, container tests and local release-bundle preparation to [PR #61](https://github.com/SUSE/suse-ai-observability-extension/pull/61), on `feat/native-ai-runtime-instrumentation`.
*   **Fact**: Local validation passed eight exporter tests, two offline strategic-merge tests and two container tests per architecture. The amd64 image ran natively; the arm64 image ran through QEMU. Both endpoints returned HTTP 200 with UID/GID 65532, zero capability sets, a read-only root filesystem, `NoNewPrivs=1` and `Seccomp=2`.
*   **Fact**: [GitHub Actions run 40702557446](https://github.com/SUSE/suse-ai-observability-extension/actions/runs/40702557446) passed both native amd64 and native arm64 jobs at commit `23f7929092fdccb5bb0594336db146dbfb593b30`, including image builds and restricted-container endpoint tests.
*   **Fact**: The proposed reference remains `registry.suse.com/ai/containers/suse-ai-ollama-exporter:0.1.0`. The source branch and PR description were updated; no registry image or Git tag was published. SUSE release ownership and promotion remain unconfirmed.
*   **Fact**: The topology-sync list and three describe requests could not connect to the configured backend during this validation. Live topology and deployment behavior remain unverified.

## 21. Ollama Packaging Repository Boundary (2026-10-28)

*   **Fact**: The user designated a separate repository for SUSE build-service packaging. This repository no longer supplies `integrations/ollama/release/_service`, build-service directives or the `%DISTURL%` placeholder in the Containerfile.
*   **Fact**: `task ollama-release-prepare` still builds and tests both image architectures and exports a local OCI layout. Its source snapshot now preserves `Containerfile` and `.dockerignore`; it contains neither a renamed `Dockerfile` nor `_service`. Snapshot contents and recorded checksums were verified against the source files.
*   **Fact**: Validation after this cleanup passed eight exporter tests, two strategic-merge patch tests and two restricted-container tests per architecture. Both `/healthz` and `/metrics` returned HTTP 200 under UID/GID 65532, a read-only root filesystem, zero capability sets, `NoNewPrivs=1` and `Seccomp=2`. Local amd64 ran natively and arm64 ran through QEMU.
*   **Fact**: The topology-sync list and three describe requests again failed because `127.0.0.1:18080` refused connections. No registry image or Git tag was published during this cleanup.

## 22. Native Release Installer Verification (2026-10-30)

*   **Fact**: `init.sh` reads the bundled native version from `stackpack.yaml` inside `/mnt/suse-ai.sts`, skips an already uploaded catalog version, pins fresh installs with `--stackpack-version`, checks the server's proposed upgrade version, and upgrades with `--unlocked-strategy overwrite --wait`. It checks the installed version/status afterward. A failed read/upload/upgrade does not trigger an automatic uninstall.
*   **Fact**: CLI `3.9.2` (commit `5b93213a60bb300b7c12dbf244f4b2a1460732db`) executed `init.sh` against a localhost HTTP fixture with both experimental StackPack environment variables unset. The test observed one ZIP upload, an explicitly versioned install, no additional HTTP mutations on re-run, and an upgrade request carrying `unlocked=overwrite`. This verifies the CLI transport contract, not real backend provisioning or schema migration.
*   **Fact**: Ten stateful installer tests passed, including failure propagation, refusing a downgrade or an unexpected server upgrade target, installed-state readback, idempotent installation/uninstallation, and explicit legacy cleanup preserving unrelated menus/autosync instances. The old-schema test uses a fixture reporting installed version `2.2.0`; it is not a live 2.2.0 migration result.
*   **Fact**: `local-demo-20261026` returned connection-refused errors from `127.0.0.1:18080` for StackPack listing, topology-sync listing, and describe requests for saved synchronization IDs `156168458177367`, `58095810080114` and `183273195246508`. The documented October 26 port-forward could not connect to Rancher. Both the October 26 and newer October 30 kubeconfigs timed out at `suse-rancher.demo` (`35.95.71.90:443`). No live StackPack was uploaded or installed by this task; real migration, active synchronization errors and browser rendering remain unverified.

## 23. Native Source Import and Offline Release Validation (2026-10-30)

*   **Fact**: Import commit `bd9ec8a` copies 184 tracked files from `StackVista/suse-stackpacks` commit `34c1246fed112f1f0a4adc219be42839217bcff0`: 152 package files, 19 SUSE AI test files, 8 dependent Collector examples, 4 invalid-mapping fixture files and the CI validator script. `knowledge/NATIVE_STACKPACK_IMPORT.json` records every source/target path and upstream SHA-256. `knowledge/NATIVE_STACKPACK_RELEASE.md` lists all 13 subsequent imported-file adaptations. All settings, resources, remediation hints and icons remain byte-identical to that source.
*   **Fact**: The public package manifest declares `version: 3.0.0` and `schemaVersion: '2.0'`. The version is the only manifest change from upstream 3.0.1. The manifest declares `open-telemetry` as a companion; it contains no legacy Groovy synchronization configuration.
*   **Fact**: Two consecutive `task stackpack-package` builds produced the same 630905-byte `dist/suse-ai-3.0.0.sts` with SHA-256 `81d50d472726dd5c8c3cdab50813d9d5efbb39b1baad1cdc405612d567a238f1`. `dist/SHA256SUMS` verifies it. The archive contains 152 sorted, stored file entries with timestamp 1980-01-01 00:00:00, normalized file permissions and no ZIP extra fields. The packaging regression also verified byte equality after changing source timestamps/modes, timezone and ZIP options.
*   **Fact**: CLI 3.9.2 packaging produced identical decompressed contents for all 152 files, with 39 additional directory entries and different order/compression/timestamp encoding. Its 351986-byte comparison archive has SHA-256 `34a31be80064f21f9db977c7b034c9fd2e6358464a6d2231a3fefde241a5d5e0`. The reproducible release archive is a plain ZIP and can be built with the checked-in shell script without `sts`, Python, Git or network access.
*   **Fact**: `CONTAINER_RUNTIME=docker task stackpack-test PYTHON=.resources/native-tests/bin/python` passed 67 native tests and skipped 12 opt-in backend tests. Fifteen distinct release checks passed across the full and final focused runs, including the real-CLI HTTP fixture, installer failure/cleanup cases, packaging comparisons and version/tag checks. Shellcheck and Bash syntax checks passed for the new/changed shell scripts.
*   **Fact**: The exact upstream validator image digest `sha256:237a6ffc5510c11b6e68aa0228365cac511b38a7d708df991e51bffa1f271b38` accepted 93 settings nodes and rejected the negative fixture with an undeclared `undeclaredValidationControl` reference. Validator, Collector and Prometheus pins are now in `scripts/ci/stackpack-images.env`; validation is invoked from the Taskfile. No `.github/workflows`, IBS or recipe files were changed, and no branch push, tag or PR was performed.

## 24. Native Release Live Install and Migration (2026-11-02)

*   **Fact**: The replacement environment supplied by the user runs Observability 2.11.1. Tests used CLI 3.9.2 and an isolated `local-demo-20261102` configuration, leaving the global CLI context unchanged. The backend initially had no SUSE AI catalog entry or instance. The unmodified 2.2.0 package from repository base `1fc931917519a022a4a254e43773f13bf38572fb` and the reproducible native 3.0.0 archive were each uploaded once.
*   **Fact**: A newly provisioned Kubernetes companion reached `WAITING_FOR_DATA`, but CLI `install --wait --timeout 300s` timed out. `init.sh` now polls companion state itself and accepts `INSTALLED` or `WAITING_FOR_DATA`. The live retry installed a new `local` Kubernetes companion, retained the existing `suse-ai` cluster and OpenTelemetry instances, and installed SUSE AI 3.0.0 as instance `73808763791700`.
*   **Fact**: Re-running the successful fresh setup made only read calls; the SUSE AI instance ID and update timestamp were unchanged. The test then explicitly removed that fresh test instance, installed the old-schema 2.2.0 package as instance `93492368154496`, and ran the new installer. The server offered 3.0.0 and `stackpack upgrade --unlocked-strategy overwrite --wait --timeout 300s` completed with the same instance ID and status `INSTALLED`. No reinstall was needed for the schema transition. A further re-run again made only read calls and left the instance unchanged.
*   **Fact**: Native upload/install succeeded without enabling experimental flags; the real upgrade and post-upgrade re-run explicitly unset both `STS_EXPERIMENTAL_STACKPACKS` and `STS_EXPERIMENTAL_STACKPACK`. The upgrade reused the already uploaded 3.0.0 catalog version and did not upload it again.
*   **Fact**: Baseline, fresh, re-run, 2.2.0, upgrade and post-upgrade snapshots included topology-sync list and a description of every returned ID. All observed synchronizations were `Running`, with cumulative `errors: 0` and `errorDetails: []`. The upgrade removed legacy `SUSE AI`, `SUSE AI Products` and `SUSE AI Topology` syncs without running `CLEANUP_LEGACY`. Final `task stackpack-sync-status` confirmed clean Agent (`263987850596316`), Kubernetes - local (`232505802755175`) and Kubernetes - suse-ai (`271228421880615`) synchronizations.
*   **Fact**: Authenticated Chromium rendered all six SUSE AI inventories after upgrade: Overview, Applications & agents, Models, Inference, Data services and GPU infrastructure. Each overview request returned HTTP 200 with no failed requests or page errors. Screenshots showed the expected headings, columns, icons and empty states. There was no AI telemetry, so populated component highlights/charts, historical data continuity and customized override migration were not tested. Browser access through localhost initially failed the backend's allowed-origin check; using the configured `https://suse-observability` origin through an ingress port-forward succeeded without changing server settings.
*   **Fact**: After the readiness fix, all 15 release regressions passed, including the real-CLI fixture returning `WAITING_FOR_DATA` for Kubernetes. Shellcheck and Bash syntax checks passed. The native archive remains 630905 bytes with SHA-256 `81d50d472726dd5c8c3cdab50813d9d5efbb39b1baad1cdc405612d567a238f1`. Scenario logs, command audits, snapshots and screenshots are under `/home/thbertoldi/suse/qa/extension-v3-setup-20261102-29gb77gq/`, outside Git; credentials and browser sessions are private. No workflows, IBS files or recipes were modified, and no push, tag or PR was performed.
