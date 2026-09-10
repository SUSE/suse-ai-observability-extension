# Regression checks

Run `task stackpack-validate` for numeric ID conflicts and Groovy lint, and
`task stackpack-test` for behavior tests. Tests read the current working-tree
Collector YAML and StackPack templates; the expected outcomes are regression
fixtures derived from the 2.2.0 review.

## Prerequisites

Use Python 3 with `tests/requirements.txt`, Node/npm, Java 17 or newer, Helm,
and Task. The task exposes the Groovy runtime bundled with pinned
`npm-groovy-lint@18.0.0`. Missing prerequisites fail the suite rather than skip
checks. For a Python virtual environment:

```bash
python3 -m venv .resources/regression-venv
. .resources/regression-venv/bin/activate
python3 -m pip install -r tests/requirements.txt
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
```

Set these two environment variables to absolute executable paths:

- `COLLECTOR_BIN`: `/otelcol/otelcol-custom` extracted from
  `ghcr.io/suse/suse-ai-opentelemetry-collector:0.156.0`, matching both examples.
  A container runtime can extract it with `podman create`, `podman cp`, and
  `podman rm`; the tests execute the binary directly on the host.
- `METRICS_BIN`: `victoria-metrics-prod` from the official
  [VictoriaMetrics v1.151.0 release](https://github.com/VictoriaMetrics/VictoriaMetrics/releases/tag/v1.151.0),
  using the binary for the host architecture.

```bash
COLLECTOR_BIN=/absolute/path/otelcol-custom \
METRICS_BIN=/absolute/path/victoria-metrics-prod \
task stackpack-test
```

The suite binds temporary localhost ports, supplies placeholder credentials,
and starts its own Collector, HTTP fixtures, and VictoriaMetrics processes.
It terminates its processes and removes their temporary data on completion.
Helm rendering uses upstream chart 0.165.0. Full configuration validation
substitutes a temporary ServiceAccount token file, without accessing a cluster.

## Covered boundaries

- Both full Collector examples validate with the pinned executable.
- The actual trace pipelines drop a 600-span ordinary trace under the shipped
  sampler, export accepted Kubeflow spans once, preserve dependency hints, and
  send KFP-to-KServe/Registry product relations to a local receiver intake.
- Application inference preserves existing Kubernetes namespaces and fills
  only missing values, including a logical `service.namespace` mismatch.
- The real HTTP check receiver emits sparse passed/failed metrics and attaches
  the configured Model Registry namespace and product type.
- The exact monitor and chart expressions evaluate against VictoriaMetrics
  fixtures for failed/healthy transitions, relapses, simultaneous endpoint
  outcomes, missing checks, and changing HTTP-status label sets.
- KServe alerts ignore unrelated controller errors and retain real failures;
  missing controller metrics remain unknown, idle observed controllers report
  zero errors, lag measures the longest active item, and queue charts retain queue names.
- GPU/vGPU fixtures distinguish identical pod/node names across namespaces and
  clusters and verify framebuffer MiB-to-bytes conversion.
- Actual Groovy scripts preserve registry namespaces and external relation
  identifiers, expose the canonical monitor target in both discovery paths,
  and leave unrelated products intact.
- Expanded template includes exist, packaged metric-binding references
  resolve, node identifiers are unique, and topology expiry is five minutes.
- Version updates accept increments and explicit higher targets, and reject
  downgrades, invalid versions, and reuse of release or candidate tags.

The tests replace Kubernetes enrichment with pre-enriched resource fixtures.
They do not exercise live Kubernetes discovery, the backend's Handlebars/STY
provisioning runtime, installed monitor attachment, or upgrade behavior. The
pre-existing GenAI model/provider relation export branches are retained; the
sampling regression check specifically covers the added Kubeflow branch and
ordinary traces.

Before accepting a deployment, run `task stackpack-sync-status`, which invokes
`sts topology-sync list` and `sts topology-sync describe` for all three SUSE AI
syncs. A StackPack upgrade
does not apply the Collector YAML changes: deploy the updated Collector config
as well. Upload with a new version and `--unlocked-strategy overwrite`.
