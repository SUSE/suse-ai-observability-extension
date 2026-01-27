# SUSE AI Observability Extension Installed

The StackPack is now installed and receiving data.

## What Was Installed

This StackPack has automatically provisioned:

### Dependency StackPacks
- **open-telemetry** - OpenTelemetry integration
- **kubernetes-v2** - Kubernetes cluster integration for `{{configurationConfig.kubernetes_cluster_name}}`

### Resources Created
- **Component Types**: GenAI-specific component types (models, systems, operations)
- **Metric Bindings**: Pre-configured metrics for LLM and vector database monitoring
- **Monitors**: Several health monitors for data stream detection and GPU error monitoring
- **Views**: Custom views for GenAI Applications, LLM Systems, Vector Databases, and GPU Nodes
- **Data Source**: Topology sync for instance type `{{configurationConfig.instance_type}}`

## Navigate to GenAI Topology

Use the **SUSE AI Observability Extension** menu in the left sidebar to access:
- **GenAI Applications** - Applications using LLMs
- **LLM Systems** - vLLM, Ollama, OpenAI endpoints
- **Models** - Individual LLM models
- **Vector Databases** - Milvus, OpenSearch
- **GPU Nodes** - Nodes with NVIDIA GPUs

## Troubleshooting

If you don't see topology data:

1. Verify the OpenTelemetry Collector is running and sending data
2. Verify the OTEL collector is configured to export to SUSE Observability
