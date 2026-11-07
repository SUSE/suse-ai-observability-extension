## Prerequisites

- Install and configure the **Open Telemetry** StackPack.
- Send application traces and metrics through an OpenTelemetry Collector.
- Enable the **Kubernetes** integration for workload and node context; collect
  NVIDIA DCGM metrics to discover GPU devices.
- Enable the product exporters or scrape receivers for the products you want to
  observe. The StackPack discovers reported telemetry; it does not install these
  products.

## Get started

1. **Connect telemetry.** Use the
   [Collector examples](https://github.com/SUSE/suse-ai-observability-extension/tree/main/examples/suse-ai)
   to configure OTLP forwarding and the receivers for your products. Keep
   product scrape receivers and resource enrichment enabled.
2. **Identify services.** Set a stable `service.name`, a nonempty
   `service.namespace`, and a unique `service.instance.id` for each running
   instance. Set `suse.ai.product` on product resources, such as `vllm`, `ollama`,
   `qdrant`, or `kubeflow-pipelines`.
3. **Explore SUSE AI.** Open the SUSE AI menu, select an application, inference
   engine, model, or GPU, and review its health and telemetry. Use the Model
   serving dashboard to compare inference activity with the previous hour.

## Service identity and migration

Include the environment and cluster in the service namespace when those
deployments must remain separate.

GenAI spans and metrics identify AI applications automatically. To classify a
product, set resource attribute `suse.ai.product` to its product key,
such as `vllm`, `qdrant`, or `kubeflow-pipelines`. Existing SUSE AI role attributes
are also recognized. Classification must describe the emitting resource, not
the remote model provider.

Forward original OpenTelemetry records without the legacy topology exporter or synthetic
provider/model copies once the migration has passed live validation. Collector
examples are available in `examples/suse-ai/` in the repository. This is a major
migration from the 2.x extension, so first test it on a separate instance.
