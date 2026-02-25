# SUSE AI Observability Architecture

This document describes the architectural approach for the SUSE AI Observability Extension.

## 1. Overview

SUSE AI Observability transforms raw OTel telemetry into a high-level architectural map. It categorizes components into three primary logical groups based on the `suse.ai.component.type` attribute:

### 1.1 User Workloads & Interfaces
- **Definition**: The entry points for users or custom business logic. These components typically consume GenAI services.
- **Component Types**:
  - `application`: Standard user applications (e.g., Python chatbots).
  - `agent`: Autonomous loops or complex reasoning agents.
  - `ui`: Frontend interfaces (e.g., Open WebUI).
- **URN Pattern**: `urn:stackpack:suse-ai:shared:component-type:<application|agent|ui>`
- **Key Metrics**: Request Rate, Success Rate, Average Tokens per Request, Cost.

### 1.2 Platform Components
- **Definition**: The managed infrastructure engines and backing services that power the AI applications.
- **Sub-categories**:
    - **Inference & Routing**:
        - `inference-engine`: GPU-heavy runners (e.g., Ollama, vLLM).
        - `model-proxy`: Routing and auth layers (e.g., LiteLLM).
    - **Knowledge & Data**:
        - `vectordb`: Vector stores (e.g., Milvus, Qdrant).
        - `search-engine`: Hybrid or lexical search (e.g., OpenSearch).
    - **Orchestration & Tools**:
        - `mcp-server`: Model Context Protocol servers (e.g., SUSE Universal Proxy).
        - `workflow-engine`: Pipeline executors (e.g., Open WebUI Pipelines).
        - `ml-registry`: Model management (e.g., MLflow).
- **URN Pattern**: `urn:stackpack:suse-ai:shared:component-type:<type>`
- **Key Metrics**: Latency (P99/P95), GPU Cache Usage, Token Throughput, Queue Depth.

### 1.3 GPU Nodes
- **Definition**: Physical or virtual Kubernetes nodes hosting NVIDIA GPUs.
- **Key Metrics**: GPU Memory, Temperature, Power Usage, XID Errors.

## 2. Technical Layers

### Layer 1: Contextualized Instrumentation
- **Standard Attributes**: Injects standard OTel Resource attributes (`gen_ai.*`) where applicable.
- **Custom Taxonomy**: Enforces SUSE AI specific resource attributes:
  - `suse.ai.managed`: Boolean flag to distinguish platform vs. user components.
  - `suse.ai.component.type`: The functional role (e.g., `inference-engine`, `vectordb`).
  - `suse.ai.component.name`: Logical name (if distinct from Service Name).

### Layer 2: Intelligent Collection (OTel Collector)
- **Normalization**: Standardizes labels across different scrapers (e.g., standardizing different Prometheus metrics into OTel).
- **Promotion**: Promotes span context to Resource metadata to allow topological inference.

### Layer 3: Virtual Topology (StackPack)
- **Multiplexed Mapping**: Infers the existence of systems and models from the resource attributes in an OTEL-instrumented application.
- **Abstract Relations**:
    - **Consumption**:
        - `application` / `agent` → `uses` → `model-proxy` or `inference-engine`
        - `application` / `agent` → `queries` → `vectordb` or `search-engine`
    - **Orchestration**:
        - `workflow-engine` → `orchestrates` → `agent`
        - `application` → `uses` → `mcp-server` (Tool use)
    - **Infrastructure**:
        - `inference-engine` → `runs` → `genai-model` (Specific Model Weights)
- **Instance Hiding**: Collapses technical `service-instance` (Pods) to present a clean architectural view.
