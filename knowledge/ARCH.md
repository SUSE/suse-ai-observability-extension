# SUSE AI Observability Architecture

This document describes the architectural approach for the SUSE AI Observability Extension.

## 1. Overview

SUSE AI Observability transforms raw OTel telemetry into a high-level architectural map. It categorizes components into three primary logical groups:

### 1.1 Applications
- **Definition**: Logical GenAI consumers. These are the entry points for users or custom logic.
- **Examples**: Open WebUI, custom Python chatbots, enterprise AI agents.
- **Component Type**: `urn:stackpack:openlit:shared:component-type:genai-app`
- **Key Metrics**: Request Rate, Success Rate, Average Tokens per Request, Cost.

### 1.2 SUSE AI Components
- **Definition**: The infrastructure engines that power AI applications.
- **Sub-categories**:
    - **LLM Systems**: Engines like Ollama, vLLM, or OpenAI.
    - **Vector Databases**: Databases like Milvus or OpenSearch.
    - **GenAI Models**: The specific weights being executed (e.g. Llama-3).
- **Component Types**: `...:genai-system-*`, `...:dbsystem-*`, `...:genai-model`.
- **Key Metrics**: Latency (P99/P95), GPU Cache Usage, Token Throughput, Model-specific utilization.

### 1.3 GPU Nodes
- **Definition**: Physical or virtual Kubernetes nodes hosting NVIDIA GPUs.
- **Key Metrics**: GPU Memory, Temperature, Power Usage, XID Errors.

## 2. Technical Layers

### Layer 1: Contextualized Instrumentation
- Injects standard OTel Resource attributes (`gen_ai.*`).
- Uses `suse-ai` SDK identity.

### Layer 2: Intelligent Collection (OTel Collector)
- **Normalization**: Standardizes labels across different scrapers.
- **Promotion**: Promotes span context to Resource metadata to allow topological inference.

### Layer 3: Virtual Topology (StackPack)
- **Multiplexed Mapping**: Infers the existence of systems and models from a single application trace.
- **Abstract Relations**:
    - `uses`: Connects Apps to Systems.
    - `runs`: Connects Systems to Models.
- **Instance Hiding**: Collapses technical `service-instance` (Pods) to present a clean architectural view.
