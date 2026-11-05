## Prerequisites

- SUSE Observability with the **Open Telemetry StackPack** installed and the **Kubernetes StackPack** configured for each monitored cluster.
- A SUSE Observability Agent reporting the cluster and workload identities. The validated combination uses Agent chart **1.7.19** (application version **3.78.2**); older Agent versions require compatibility validation.
- **SUSE AI OpenTelemetry Collector 0.164.1**, the version tested by this spike, with the required runtime profiles and a reachable OTLP endpoint. Minimum-version support must follow the published compatibility matrix.
- For available Ollama models, the inventory-capable **3.0.0 exporter build**, with read access to `/api/tags` and `/api/ps`. An older image also labelled 3.0.0 has residency metrics only: pin the validated inventory build digest when published.
- For GPU devices, NVIDIA DCGM with GPU UUIDs. Pod allocation links additionally require nonempty workload namespace and pod labels.

## Quick start

1. Install the companion StackPacks and Agent. Set the Collector's Kubernetes cluster name to the name used by the Kubernetes StackPack, and configure authenticated OTLP delivery.
2. Enable the Ollama runtime profile, add the read-only exporter beside Ollama, and enable DCGM collection for GPU workloads. Instrument your AI applications for request, token and trace visibility.
3. Open **SUSE AI → Inference servers**. Select Ollama, inspect its served models and runtime API status, then follow GPU allocation links to the pod and node. Verify fresh telemetry and mapping status before relying on monitors.

Follow the [SUSE AI monitoring guide](https://documentation.suse.com/suse-ai/1.0/html/AI-monitoring/index.html) for deployment instructions and integration-specific settings. Product coverage, identity limitations and telemetry caveats belong in the monitoring guide.
