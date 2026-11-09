## Understand your AI services in context

Follow application traffic to its AI dependencies, inspect the models available on an inference server, and find the GPU and Kubernetes node supporting a workload.

### Data sources and signals

- **Ollama runtime exporter:** available models from `/api/tags`, loaded models from `/api/ps`, disk size, VRAM residency and runtime API read success. Available and loaded are different states; request latency and token usage come from instrumented callers.
- **OpenTelemetry instrumentation:** GenAI request duration, token usage, model usage, agents and service calls where applications emit the supported attributes.
- **NVIDIA DCGM:** GPU UUID, utilization, temperature, framebuffer use and power. Workload labels connect an allocated GPU to a pod; the exporter pod is not the allocated workload.
- **Kubernetes Agent:** pod readiness, node state, scheduling and the links from services to their workloads.
- **Other supported runtime integrations:** vLLM request queues and latency, Milvus search latency, Qdrant collections and request rates, and OpenSearch cluster health. Signals depend on the configured integration and product version.

### Components, relations and presentations

The SUSE AI domain organizes Applications, Agents, Gateways, Tools, Inference Servers, Models, Data Services and GPUs. Available models and physical GPUs are distinct components. `serves` connects an inference server to a model; `allocated to` connects a GPU to its workload pod; `runs on` connects a GPU to its node.

The Inference servers page lists model availability and runtime observations. Model and GPU pages connect inventory to infrastructure. Operator-focused monitors explain what to check, likely causes, a fix and how to verify recovery.

### Fits with your existing topology

Kubernetes remains the source of workload state; Open Telemetry remains the source of service traces and logs. Inference servers retain the existing Open Telemetry service. SUSE AI adds runtime highlights and its own inventory without replacing the standard service icon or tables. No request metrics are attributed to a served model solely because names match.
