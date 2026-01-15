## GenAI Observability

Comprehensive observability for Generative AI applications and infrastructure.

### What This StackPack Provides

- **GenAI Application Topology**: Track applications, models, and operations
- **LLM System Monitoring**: vLLM, Ollama, and OpenAI with metrics for token throughput, latency, and cache utilization
- **Vector Database Monitoring**: Milvus and OpenSearch with request rates and operation metrics
- **GPU Node Monitoring**: GPU utilization and NVIDIA XID error detection
- **6 Health Monitors**: Automatic health monitoring for all GenAI components

### Automatic Dependencies

This StackPack automatically installs:
- **open-telemetry** - For traces and metrics
- **kubernetes-v2** - For Kubernetes cluster topology

### Prerequisites

- Kubernetes cluster with GenAI workloads deployed
- OpenTelemetry Collector configured to collect GenAI metrics
- One or more GenAI data sources configured (OpenLIT SDK, vLLM, Milvus, OpenSearch)

### Configuration

| Parameter | Description |
|-----------|-------------|
| Kubernetes Cluster Name | Name of your Kubernetes cluster |
| Instance Type | Topology source identifier (e.g., `openlit`) |
