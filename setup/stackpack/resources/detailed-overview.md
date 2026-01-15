# GenAI Observability StackPack

## Overview

The GenAI Observability StackPack provides comprehensive observability for Generative AI applications and infrastructure, including LLM systems, vector databases, and GPU nodes.

## Architecture

This StackPack configures your SUSE Observability instance with:

### Automatic Dependency Installation
When installed, this StackPack automatically provisions:
- **open-telemetry** StackPack for trace and metric collection
- **kubernetes-v2** StackPack for Kubernetes cluster integration

### Component Types

| Type | Description |
|------|-------------|
| `genai.app` | GenAI application (service using LLM) |
| `genai.system.vllm` | vLLM inference server |
| `genai.system.ollama` | Ollama local LLM server |
| `genai.system.openai` | OpenAI API endpoint |
| `genai.model` | LLM model (e.g., llama2, gpt-4) |
| `genai.operation` | LLM operation (chat, completion) |
| `genai.dbsystem.milvus` | Milvus vector database |
| `genai.dbsystem.opensearch` | OpenSearch vector database |
| `genai.dboperation` | Vector database operation |

### Monitors

The StackPack includes 6 monitors:

| Monitor | Description |
|---------|-------------|
| VectorDB System Metric Stream | Detects if OpenTelemetry is sending VectorDB metrics |
| GenAI System Metric Stream | Detects if OpenTelemetry is sending GenAI system metrics |
| GenAI Model Metric Stream | Detects if OpenTelemetry is sending model-level metrics |
| GenAI Model Op Metric Stream | Detects if OpenTelemetry is sending operation-level metrics |
| VectorDB Op Metric Stream | Detects if OpenTelemetry is sending VectorDB operation metrics |
| GPU Node NVIDIA XID Errors | Detects NVIDIA XID errors on GPU nodes |

### Metrics

The StackPack includes metric bindings for:
- Token throughput (prompt and generation)
- Request latency (E2E, TTFT, TPOT at various percentiles)
- Request counts and rates
- Cache utilization (KV cache, prefix cache)
- GPU utilization and errors (via DCGM)
- Vector database operations
 Vector database operations
