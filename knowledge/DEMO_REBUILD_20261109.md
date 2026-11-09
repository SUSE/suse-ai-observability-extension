# New demo environment — 2026-11-09

The new environment is running SUSE AI **3.0.0-dev.990**. The existing 2.0.0 instance (`198933190161282`) was backed up and upgraded in place with `--unlocked-strategy overwrite`. No catalog removal or rollback was required. Only the newly supplied management and downstream clusters were changed.

Normal HTTPS access at `https://suse-observability` was verified against the new cluster's certificate and Kubernetes synchronization ID. The downstream cluster is `suse-ai`, Kubernetes 1.34.4, with four RKE2 nodes and four GPUs.

## Versions and deployment changes

| Component | New environment before setup | Deployed result |
| --- | --- | --- |
| SUSE AI StackPack | 2.0.0 | 3.0.0-dev.990; native schema v2 |
| SUSE AI Collector | 0.149.0 | Local 0.165.0 development build from `cb3a0ecd89cb4298821a0561e340bfc7b4b78897`, `origin/update-collector` |
| Demo applications | Absent | `e77906b520b1b7e96bf1b10b5f278b0b98b00c9c` plus the existing local product/auth patches and identity fix `efd7b9ee5aa1316dc4c6a1dc08032c48fbd62ee0` |
| Ollama | 0.21.2 | 0.40.14; chart 1.95.0 |
| Ollama inventory exporter | Absent | Branch-built `3.0.1-dev.20261109.1` sidecar |
| Milvus | 2.6.20 | 2.6.21; chart 5.0.25 |
| Open WebUI | 0.6.41 | 0.6.41 with native OTel and the current in-process Ollama adapter |
| mcpo | 0.0.17 | 0.0.17 with real server instrumentation and MCP classification |
| vLLM | Absent | 0.19.0 serving `qwen-small` |
| LiteLLM | Absent | Image v1.106.6; chart 1.106.4; authenticated metrics and Ollama/vLLM routes |
| Qdrant | Absent | v1.20.0 |
| OpenSearch | Absent | 3.9.0 with a new CA, TLS and credentials |
| MLflow | Absent | 3.18.0 with persistent runs/artifacts and instrumented HTTP workers |
| PyTorch | Absent | 2.14.0; real CPU training every two minutes, uploading checkpoints to MLflow |
| Kubeflow | Absent | Compatible chart 0.4.1: Pipelines 2.17.0, KServe v0.19.0, Model Registry Hub v0.3.10 |
| Istio | Absent | 1.30.7 with the chart's native ingress authentication provider |

Eight local images were imported into all four nodes using `task demo-import-images`; none was pushed to a registry. The six application images cover gateway, RAG, LLM, agent, traffic generation and the Iris lifecycle. The additional Qdrant/OpenSearch RAG services and product traffic reuse the RAG image. Nine demo Deployments remain enabled.

Two compatibility pins are explicit. The latest Kubeflow chart 0.5.0 requires Kubernetes 1.35; this deployment uses the newest compatible source revision, `36a6ddd2707c58db5aae59627d0cf192380e9a5a`. Open WebUI's latest catalog version is 0.13.0, but the current provider adapter supports and tests 0.6.41, so that application remains pinned. This is not a claim that every upstream application is on its newest release.

## What was repaired during setup

Both the initial Collector and Kubernetes agents pointed to a service DNS name inside their own cluster instead of the management cluster. Their connections now use the new management ingress with its actual CA. The OTLP ingress uses its existing certificate, and the Collector reports the real downstream cluster identity. Four native nodes and four GPU-to-node relations are now present.

Fresh demo Helm installs lacked the marker used by the agent/RAG activity overlays. The five instrumented demo workloads now report `suse.ai.demo=true`, with pod UID, namespace and node supplied by the Downward API. The reusable chart leaves cluster identity to the configured Collector. mcpo reports the supported `mcp-server` role. These changes restore useful agent/RAG charts and the MCP category without changing the native StackPack payload.

Open WebUI has a dedicated ordinary demo user with access to the chat model. Its original SQLite database and legacy filter source were backed up. The obsolete SUSE telemetry Pipeline was disabled; the unrelated conversation-limit filter was retained.

## Live acceptance

- All application workloads were Ready in the final cluster inventory. Ollama inventory contains `gemma:2b`, `llama3.2:latest` and `nomic-embed-text:latest`; the Models table also includes vLLM's `qwen-small`. All four model rows were CLEAR in the UI review.
- Real direct vLLM, LiteLLM-to-vLLM and LiteLLM-to-Ollama requests returned HTTP 200 with nonempty completions and reported token usage after the final product upgrades. Anonymous/wrong-key LiteLLM metrics requests returned 401; the correct key returned 200.
- Continuous traffic succeeds through chat, RAG, agent tools, Qdrant, OpenSearch, MLflow, mcpo and Open WebUI. Database client traces exist for Milvus, Qdrant and OpenSearch; no nonexistent database/Ollama server spans are claimed.
- PyTorch completed 200 training epochs, recorded loss and uploaded a real checkpoint to MLflow. Iris pipeline run `7916483f-f7b7-4334-b316-3782d135b9fa` completed preparation, training, quality gate, registration, deployment and prediction. Agent registry/prediction scenarios are enabled. A corrected explicit 1,800-second recurring trigger keeps lifecycle activity running.
- All 31 threshold monitors passed failing/recovering/no-data native previews, and the derived-health monitor was exercised separately. Runtime status for all 32 monitors returned no evaluation errors or unmapped states in the captured audit. A monitor can correctly report a real unhealthy condition; previews did not persist synthetic health.
- The Collector's five test suites, Ollama image smoke checks, ten demo SDK tests and 25 extension release/deployment tests passed. The staged demo Helm identity repair was rendered and checked for all five workloads.
- `sts topology-sync list` and `describe` were captured, together with component/relation mapping statuses. Native SUSE AI mappings have no returned errors. All 175 packaged files match the source, apart from the intentional development manifest version.

## Where to look

| Menu | Components and data |
| --- | --- |
| SUSE AI → Overview | Product identity, role and health; mcpo displays MCP server |
| SUSE AI → Applications & agents | `demo-agent`, `agent-service`, `rag-service`, `rag-qdrant`, `rag-opensearch`, gateway and traffic; agent activity and RAG retrieval/context/performance charts |
| SUSE AI → Models | Three available Ollama models plus `qwen-small`; metadata, direct health, loaded/unloaded state and scoped usage traces |
| SUSE AI → Inference | Ollama, vLLM, LiteLLM and KServe; product-specific metrics and engine-to-model relations |
| SUSE AI → Data services | Milvus, Qdrant and OpenSearch; related MLflow and Kubeflow services are also reachable from Overview |
| SUSE AI → GPUs | Four native node rows, the full 17-column table, physical devices and workload/node links |

The adversarial review verified all five owned component types, six grouped menus, four GPU-node links, 24 finite GPU-node metric cells and 20 finite GPU-device queries. The logical agent's four activity queries and the RAG custom queries return finite data.

## Remaining observed issues

The platform's built-in **Agent** synchronization reports unresolved process connections to `urn:external-api:/cluster/suse-ai:<IP>` targets. The sampled counter was 63 with eight returned details; Kubernetes synchronization and native SUSE AI mappings are separate and clean. No built-in settings were altered to conceal these failures.

One exact-scope model usage, `product-traffic / litellm / vllm-chat` without endpoint dimensions, has no matching metrics or traces in the captured 24-hour check. Eight other model usages are useful trace-only observations. The empty identity reproduces the previously documented case and remains unresolved. The observed-database explanatory field also clips in the UI.

## Evidence and delivery

Private evidence is under `/home/thbertoldi/suse/qa/demo-rebuild-20261109-d5tmgw2a/` (owner-only directory). `baseline/` contains the instance, settings, monitors and Kubernetes configuration backups; `webui/` contains the database/filter backup and dedicated demo credentials. `sources/provenance.json`, `final/workload-versions.json`, `image-import/verified.json`, `final-sync/`, `monitor-checks/` and `monitor-runtime-summary.json` record provenance and validation. Credentials are not included in this report.

`ux/REVIEW.md` contains the independent acceptance findings and screenshots, including `screens/logical-agent-restored.png`, `screens/rag-metrics-tab.png`, `screens/models-final.png`, `screens/gpu-nodes.png` and `screens/overview-accepted.png`.

The deployment tooling is part of [extension PR 64](https://github.com/SUSE/suse-ai-observability-extension/pull/64). The isolated demo identity repair is [demo-apps PR 11](https://github.com/thbertoldi/suse-ai-demo-apps/pull/11). Existing unrelated working changes were preserved.
