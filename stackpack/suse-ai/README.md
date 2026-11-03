# SUSE AI Observability

StackPacks 2.0 implementation of the SUSE AI extension. AI settings compose with
the Open Telemetry StackPack on its existing services and service instances.
Named agents, requested models, and served vLLM models have their own scoped
identities. Kubernetes GPU charts extend existing pods and nodes.

The package contains independent `settings/genai`, `settings/products`, and
`settings/gpu` modules. Only the installed products that emit the corresponding
telemetry receive product presentations. OpenLIT and OpenLLMetry compatibility
transforms are included in the
[`Collector examples`](../../examples/suse-ai/).

Optional HTTP endpoint checks use the resource attribute
`suse.ai.observation.kind=http-probe` on an explicitly classified AI service.
The endpoint charts and availability monitor report observed HTTP 2xx status and
probe duration, not inference request success or latency. Per-pod probes must use
the actual pod UID as `service.instance.id`; cluster-wide product metrics must not
be assigned to an arbitrary pod. Missing probe telemetry remains missing data.

Ollama runtime charts consume `ollama_api_up`, `ollama_loaded_models`, and
`ollama_model_{size_bytes,vram_bytes,context_length}` from an optional exporter of
the local `/api/ps` response. These values describe loaded model copies, reported
memory residency and context length; request and token charts still require
GenAI instrumentation. Runtime model values are shown only for a successful,
current API observation. These exporter metrics are separate from Ollama's
HTTP endpoint checks.

From the public extension repository root, install test dependencies and run:

```sh
python3 -m venv .resources/native-tests
.resources/native-tests/bin/pip install -r tests/requirements.txt
CONTAINER_RUNTIME=docker task stackpack-test PYTHON=.resources/native-tests/bin/python
CONTAINER_RUNTIME=docker task stackpack-validate
task stackpack-package
```

The Taskfile uses immutable validator, Collector and Prometheus pins from
[`scripts/ci/stackpack-images.env`](../../scripts/ci/stackpack-images.env).
Podman is also supported with `CONTAINER_RUNTIME=podman`. Backend tests are
separately enabled with `AI_LIVE_TESTS=1` and the documented fixture environment.

The release artifact is `dist/suse-ai-3.0.0.sts`, accompanied by `SHA256SUMS`.
Packaging uses a plain ZIP with sorted entries, fixed timestamps and permissions.
It needs GNU coreutils/findutils and Info-ZIP, with no CLI or network access.
For comparison, CLI 3.9.2 can package the same file contents:

```sh
STS_EXPERIMENTAL_STACKPACKS=1 sts stackpack package -d stackpack/suse-ai -f /tmp/suse-ai-cli.sts
```

The public extension release uses version 3.0.0. Its native settings come from
StackVista/suse-stackpacks 34c1246 (upstream package version 3.0.1).
See the [release and migration record](../../knowledge/NATIVE_STACKPACK_RELEASE.md)
for the exact import inventory, adaptations and setup-container contract.
Use CLI 3.9.2 for setup. Packaging and offline validation do not establish runtime
compatibility with every 2.11 release. Validate topology and metric behavior on
the target instance before retiring the custom topology exporter.
