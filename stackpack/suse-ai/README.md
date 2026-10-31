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

Run the same Python tests as CI from the repository root:

```sh
python3 -m venv /tmp/suse-ai-tests
/tmp/suse-ai-tests/bin/pip install -r tests/suse-ai/requirements.txt
/tmp/suse-ai-tests/bin/python -m unittest discover -s tests/suse-ai -v
```

Docker integration tests run when `AI_COLLECTOR_IMAGE` and `AI_PROMETHEUS_IMAGE`
are set. Use the pinned images from the `validate` job in
[the CI workflow](../../.github/workflows/stackpacks-ci.yml).

For package validation, set `VALIDATOR_IMAGE` to the image pinned in the CI
workflow's `validate` job and use the existing repository script:

```sh
bash scripts/ci/validate_stackpack.sh stackpacks/suse-ai
```

Package with the same command used by CI:

```sh
cd stackpacks/suse-ai
STS_EXPERIMENTAL_STACKPACKS=1 sts stackpack package
```

Use CLI 3.9 or later. The validator image is the repository CI pin. Packaging and
offline validation do not establish runtime compatibility with every 2.11
release. Validate topology and metric behavior on the target instance before
retiring the custom topology exporter.
