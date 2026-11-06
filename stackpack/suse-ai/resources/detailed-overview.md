SUSE AI adds application latency, token usage, reported model cost, agent and
RAG metrics, product health monitors, and GPU charts to SUSE Observability.

AI services retain their OpenTelemetry identities and standard perspectives.
Requested models describe the models an application calls. They do not identify
the physical inference engine behind a provider-compatible API. Named agents
represent logical agents, while individual executions remain in traces.

Product integrations include vLLM, Ollama, Milvus, Qdrant, OpenSearch,
Elasticsearch, KServe, Kubeflow Pipelines, and Kubeflow Model Registry.
Additional AI roles cover model proxies, interfaces, MCP servers, and registries.
Product-specific metrics require the corresponding exporter or instrumentation.

The package uses OpenTelemetry GenAI attributes. The Collector example includes
OpenLIT and OpenLLMetry compatibility transforms. It does not run evaluations,
store prompt versions, or infer missing token usage or costs. GPU allocation
costs and provider token charges are separate measurements.

The Models page includes vLLM served models and Ollama's available models when
the Ollama exporter reports `ollama_model_info` from `/api/tags`. Available Ollama
models remain visible while unloaded; a deleted model expires after 15 minutes without an
inventory observation. Inventory tables show component health and identity. Open
a model for the metrics its product reports and the **Served by** link to its engine.
Client-side requests and latency remain on the calling application's model-usage view.

Model-to-engine arrows express a hosting dependency: **model → inference engine**
means the model depends on that engine to serve requests. Earlier previews drew
the inverse **engine → model** serving relationship. The current direction supports
inherited engine health when the model has no direct health checks. The model and
engine still represent the same components; the arrow does not describe request flow.
