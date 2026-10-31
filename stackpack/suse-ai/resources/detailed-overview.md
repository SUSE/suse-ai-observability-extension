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
