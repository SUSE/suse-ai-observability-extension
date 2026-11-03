Install the Open Telemetry StackPack and send traces and metrics through OTLP.
Use stable `service.name`, a nonempty `service.namespace`, and a unique
`service.instance.id` for each running instance. Include the environment and
cluster in the service namespace when those deployments must remain separate.

GenAI spans and metrics identify AI applications automatically. To classify a
product, set resource attribute `suse.ai.product` to its product key,
such as `vllm`, `qdrant`, or `kubeflow-pipelines`. Existing SUSE AI role attributes
are also recognized. Classification must describe the emitting resource, not
the remote model provider.

Keep product scrape receivers and resource enrichment. Forward original
OpenTelemetry records without the legacy topology exporter or synthetic
provider/model copies once the migration has passed live validation. Collector
examples are available in `examples/suse-ai/` in the repository. This is a major
migration from the 2.x extension, so first test it on a separate instance.
