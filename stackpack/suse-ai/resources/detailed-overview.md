## See the whole AI service

A slow answer can start with an application, a queued model request, a retrieval
service, or a busy GPU. SUSE AI Observability brings those signals together so
operators can find the affected component and follow its dependencies to the
next useful check.

Start with health and inventory, open a component for its product metrics, and
follow a request into traces. AI services share their existing OpenTelemetry and
Kubernetes context, keeping application behavior and infrastructure health close
at hand.

## Answer operational questions

- **Why are responses slow?** Compare application latency with vLLM time to first
  token, request queues, cache usage, and GPU load. Use traces to inspect the
  model calls, retrieval steps, and tools involved in a request.
- **Which models can serve requests?** Discover vLLM deployments and Ollama's
  available model inventory. See each model's hosting engine, availability,
  loaded state, and memory footprint where the product reports them.
- **What is driving usage and spend?** Explore caller token usage and LiteLLM
  gateway traffic, failures, and reported spend. Compare the current period with
  the previous hour using the built-in dashboards.
- **Where is capacity under pressure?** Inspect physical GPUs and their nodes,
  including utilization, memory, temperature, power, driver details, and workload
  allocation from NVIDIA DCGM and Kubernetes telemetry.
- **What needs attention first?** Use component health and monitors with
  concrete checks, likely causes, remediation, and verification steps.

## Metrics that fit each product

Shared inventory pages organize products by role. Component pages show the
signals that their integration supplies:

- **vLLM and Ollama:** inference performance for vLLM; model inventory, loaded
  state, and model memory for Ollama.
- **LiteLLM:** gateway requests, latency, failures, tokens, and reported spend.
- **Milvus, Qdrant, and OpenSearch:** retrieval, storage, and service health
  metrics for the data services behind AI applications.
- **MLflow and mcpo:** instrumented service activity, endpoint availability,
  and request traces for tracking and tool services.
- **Kubeflow Pipelines, KServe, and Model Registry:** workflow, model-serving,
  and registry signals when these products and their telemetry are configured.
- **OpenTelemetry GenAI instrumentation:** application and model-call latency,
  tokens, named agents, tool calls, and RAG activity, as reported by the application.

## Connected to your existing observability

The StackPack adds AI application, agent, model deployment, model usage, tool,
and GPU views, plus four dashboards: **Overview**, **Model serving**,
**Gateway & spend**, and **GPU fleet**. Model deployments link to their inference
engines; model usages link to their calling applications. GPU devices connect
to nodes and observed workload allocations.

Open Telemetry service pages retain their standard layout. AI metrics appear as
additional sections, alongside existing service traces and health. The StackPack
uses the telemetry you send; installing it does not deploy the AI products or
their exporters.

Caller observations and server measurements remain distinct: a requested model
name alone does not establish which physical engine served it. Available but
unloaded Ollama models remain in inventory and can be healthy. Missing metrics
stay absent, and spend is shown only when reported. See the
[monitoring guide](https://github.com/SUSE/suse-ai-observability-extension/tree/main/docs)
for instrumentation, supported signals, and configuration details.
