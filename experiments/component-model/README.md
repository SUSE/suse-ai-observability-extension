# Ollama component-model spike

This is a staged experiment for D1–D7 and S1–S5, not the full StackPack redesign. The release package stays at **3.0.0**. The findings, migration limits and full-redesign tasks are in [the spike report](../../knowledge/SPIKE_V3_COMPONENT_MODEL.md).

## Build and validate

Use a fresh, never-uploaded `3.0.0-spike.N`, replacing `N` below with a positive integer. Versions 1–6 were consumed by this experiment and must never be uploaded again. Keep staging directories and captures outside Git:

```sh
task component-model-build SPIKE_VERSION=3.0.0-spike.N \
  SPIKE_OUTPUT=/absolute/local/spikeN SPIKE_MODE=overlay
# Use SPIKE_MODE=control for native Ollama without our presentations.
task component-model-validate SPIKE_OUTPUT=/absolute/local/spikeN
task component-model-package SPIKE_OUTPUT=/absolute/local/spikeN \
  SPIKE_VERSION=3.0.0-spike.N
task component-model-test PYTHON=.resources/native-tests/bin/python
```

The builder copies the release package, excludes native Ollama services/instances from existing SUSE AI presentations, and adds the prototype. It preserves other products' configuration. Overlay specificity defaults to 1; the Open Telemetry 0.1.4 service presentation source has specificity 10. Optional `SPIKE_FLAGS='--specificity -10 --probe-field'` reproduces the highlight collision probe. `--screenshot /local/capture.png` tests relative and explicit versioned resource image URLs in the install text. It copies that image only to the staged archive.

New experimental GPU/layer mapping **setting** identifiers receive the spike number to avoid the observed remove/re-add refresh problem. Component URNs remain unchanged. This is an experiment lifecycle accommodation; normal release mappings should have stable identifiers and upgrade in place.

## Live procedure

1. Assert the current branch is `feat/ollama-model-inventory-3.0.1`. Use an explicitly configured demo CLI wrapper or context; never `default`. Back up instance/catalog state, settings, mapping descriptions, monitor IDs, topology, Collector/workload specs, and both Open Telemetry pages before changes. The native presentation export API on this demo is unimplemented; preserve the exact original archive as well as resolved API output.
2. Validate/package, check the catalog and local upload ledger, then upload the new archive once. Because these prereleases sort below an installed 3.0.x release, enter through `stackpack downgrade --stackpack-version ...`. This is not a forward-upgrade test. Use `--unlocked-strategy overwrite` for upgrades.
3. Capture the control Services/component pages, then the overlay pages, AI inventory, models, GPUs, monitor and API output. If inventory telemetry is absent, snapshot and temporarily deploy the inventory-capable exporter, then restore the original deployment spec. Do not infer workload allocation from the DCGM exporter pod.
4. Inspect **both** `sts topology-sync list` and `describe` for every synchronization, plus native mapping status. Compare active error details against the baseline; never clear existing errors to manufacture a clean result.
5. Restore the existing catalog release without uploading it again. Restore the exporter/workload spec, remove temporary ConfigMaps and test catalog versions, and compare settings, monitor IDs, service links, source mappings and synchronization errors. Retain the evidence locally and the upload ledger permanently: deleting a catalog version does not make it reusable.

`graph-settings/layers.sty` is a separate diagnostic for the classic settings API. Native v2 packages reject those node types. The `domainName` / `layerName` fields in the spike mappings are intentional S2 probes: the tested backend drops them. They must not be advertised as working domain/layer support. See the report before reusing these files.

## Drafts

The three original SVGs are under `icons/`, with provenance in `icons/LICENSES.md`. Install copy is under `resources/`; it describes the intended redesign, and its domain/layer claims are gated on resolving S2. No ComponentType icon fields, stock PNGs, Go runtime, or normal release mappings are modified.

Evidence remains under the operator's local `~/suse/qa/` directory. `knowledge/evidence/` is also ignored and retained locally.
