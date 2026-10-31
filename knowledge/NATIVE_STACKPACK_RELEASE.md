# Native StackPack 3.0.0 release preparation

The source is `StackVista/suse-stackpacks` commit
`34c1246fed112f1f0a4adc219be42839217bcff0` (PR #33). The local clone's working
branch was different; the import was extracted from that exact Git commit.
Import commit `bd9ec8a` contains the selected files verbatim, with only the
`stackpacks/suse-ai` → `stackpack/suse-ai` path relocation. Adaptations are
separate commits on `feat/native-stackpack-release-v3`.

## Inventory and upstream differences

The complete 184-file inventory, source paths and original SHA-256 hashes are in
[NATIVE_STACKPACK_IMPORT.json](NATIVE_STACKPACK_IMPORT.json).

| Upstream selection | Files | Disposition |
| --- | ---: | --- |
| `stackpacks/suse-ai/stackpack.yaml`, `README.md` | 2 | Copy into `stackpack/suse-ai` |
| `stackpacks/suse-ai/settings/` | 89 | Copy unchanged; 93 settings nodes |
| `stackpacks/suse-ai/icons/` | 29 | Copy unchanged |
| `stackpacks/suse-ai/includes/` | 23 | Copy unchanged |
| `stackpacks/suse-ai/resources/` | 9 | Copy unchanged |
| `tests/suse-ai/` | 19 | Copy all tests, fixtures and pinned requirements |
| `examples/suse-ai/` | 8 | Copy; the integration tests depend on these files |
| `tests/fixtures/invalid-component-mapping/` | 4 | Copy the server validator's negative control |
| `scripts/ci/validate_stackpack.sh` | 1 | Copy the validator entrypoint |

The validator, Collector and Prometheus image references from upstream CI are
recorded verbatim in `scripts/ci/stackpack-images.env`, including digests. They
are consumed by the Taskfile. No private repository checkout is required to
build the release or run these tests; pulling the validator image may require
the registry access available in the build/test environment.

Leave upstream's other StackPacks, platform/container distribution machinery,
Helm update automation, generic version-bump script, and root README in upstream.
That README describes the multi-StackPack image repository, not this release.
Keep the relevant package/example README content here. Leave local generated
`.sts`, `target/`, caches and other untracked artifacts behind. No workflows,
IBS files or recipes were changed in this task.

Every imported file differing from the upstream snapshot:

| Target file | Adaptation |
| --- | --- |
| `stackpack/suse-ai/stackpack.yaml` | Version `3.0.1` → `3.0.0` only |
| `stackpack/suse-ai/README.md` | Public repository tasks, image-pin location, release/provenance links |
| `examples/suse-ai/README.md` | Correct package README path; remove an upstream conversation-specific note about unattached monitor overrides |
| `scripts/ci/validate_stackpack.sh` | Select Docker/Podman through `CONTAINER_RUNTIME` |
| `tests/suse-ai/test_contract.py` | `stackpacks/suse-ai` → `stackpack/suse-ai` |
| `tests/suse-ai/test_collector.py` | Docker/Podman through `AI_CONTAINER_RUNTIME` |
| `tests/suse-ai/test_identity_collector.py` | Same runtime selection |
| `tests/suse-ai/test_litellm_collector.py` | Same runtime selection |
| `tests/suse-ai/test_promql.py` | Same runtime selection |
| `tests/suse-ai/test_backend_identity.py` | Explicit `STS_CONTEXT` support and service-token API authentication |
| `tests/suse-ai/test_backend_gpu_pods.py` | Use the same selected CLI context |
| `tests/suse-ai/test_backend_metrics.py` | Use the shared context-aware CLI command |
| `tests/suse-ai/test_backend_presentation_identity.py` | Use the shared context-aware CLI command |

All mappings, presentation definitions, monitors, resources, hints and icons
remain byte-identical to upstream. There is no adapted Go or Groovy runtime.
The old 2.x package is retained in Git history, not included alongside native
settings. The old template/Groovy and query tests are superseded by the native
suite; tests for the unchanged legacy Collector examples remain under
`tests/legacy/` with `task stackpack-test-legacy-collector`.

## Version decision

The public release is 3.0.0, matching the intended tag `v3.0.0`. Schema version
is independently `2.0`; no native setting depends on package version 3.0.1.
This is a deliberate release-number adaptation of upstream 3.0.1, not a request
to downgrade installations of that upstream version. The installer refuses a
downgrade. `task version-up` now edits `stackpack.yaml` and preserves the checks
against lower versions and reused local release/candidate tags.

The setup script checks catalog versions and never uploads the same version
again. An existing version is treated as immutable; this is not a server-side
byte/hash attestation. Any payload change after upload requires a new version.
Do not publish different archives under the same release version.

## Reproducible artifact and IBS command

Run `task stackpack-package` (alias `stackpack-build`). It calls
`bash scripts/package-stackpack.sh`, with optional source/output directory
arguments. The script stages only `README.md`, `stackpack.yaml`, `settings/`,
`resources/`, `icons/` and `includes/`, normalizes regular files to mode 0644,
directories to 0755, and timestamps to 1980-01-01 00:00:00 UTC. It rejects
symlinks and special files. Source checkout metadata is not modified.

From that normalized staging directory, the exact Info-ZIP command is:

```bash
export LC_ALL=C TZ=UTC
unset ZIPOPT
find README.md stackpack.yaml settings resources icons includes -type f -print |
  sort | zip -q -X -0 "$archive" -@
```

`$archive` must be an absolute, previously nonexistent output path. The provided
script handles temporary staging, replacement of the final artifact and
`dist/SHA256SUMS`; IBS should invoke it rather than omit normalization. Build
requirements: Bash, GNU coreutils/findutils, grep, sed and Info-ZIP. Neither
`sts`, Python, Git nor network access is required at RPM build time.

Artifact: `dist/suse-ai-3.0.0.sts`, 630905 bytes, 152 file entries.
SHA-256:

```text
81d50d472726dd5c8c3cdab50813d9d5efbb39b1baad1cdc405612d567a238f1
```

Comparison with CLI 3.9.2:

```bash
STS_EXPERIMENTAL_STACKPACKS=1 sts stackpack package \
  -d stackpack/suse-ai -f /tmp/suse-ai-cli.sts
```

All 152 file names and decompressed file bytes match. The CLI archive is
351986 bytes and includes 39 directory entries, uses Deflate for files and a
different entry order, and writes zero DOS timestamp fields (Python displays
`1980-00-00`). Our archive stores files without compression, uses sorted paths,
valid fixed DOS dates, normalized Unix permissions and no extra fields. These
ZIP metadata/encoding differences explain the different SHA-256; there is no
manifest conversion, signing or proprietary wrapper. Both contain the README,
as the CLI does. Rebuild tests also vary source modes, timestamps, timezone and
`ZIPOPT` and assert identical archive bytes.

## Setup behavior and migration

The default archive remains `/mnt/suse-ai.sts`. The script reads its manifest;
there is no separate hard-coded version. CLI 3.9.2 exposes package/upload/
install/upgrade with both `STS_EXPERIMENTAL_STACKPACKS` and the older singular
variable unset. No experimental variable is set by the installer. The official
[custom integration tutorial](https://documentation.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/create.html)
also separates packaging/upload from installation. A test also runs the real CLI against a local HTTP fixture with both variables
unset: `init.sh` uploads the ZIP, installs, makes no HTTP mutations on re-run,
and sends an upgrade with `unlocked=overwrite`. This verifies the CLI/HTTP
contract, not backend provisioning or schema migration.

| Scenario | Installer behavior | Evidence available in this task |
| --- | --- | --- |
| Fresh | Ensure `kubernetes-v2` per cluster and `open-telemetry`; upload once; install exact bundled version with wait; read back status/version | CLI boundary and real-CLI HTTP-fixture tests passed; live pending |
| Successful re-run | Read installed state; no upload, install, upgrade or deletion | Real CLI sent no additional HTTP mutations; live pending |
| 2.2.0 → 3.0.0 | Upload if absent; verify server's `nextVersion` equals bundled version; upgrade with `--unlocked-strategy overwrite --wait`; verify final state | Tests assert command, strategy and retained instance ID; actual schema transition pending |
| Newer installed version | Fail before changing companions or AI | Test passed |
| Different server upgrade target | Fail instead of installing an unintended version | Test passed |
| Read/auth/upload/upgrade failure | Fail; no claim that upload failure means “already exists”; no automatic uninstall | Failure-injection tests passed |
| Uninstall/re-run uninstall | Uninstall AI instances, wait until absent; second run makes no changes | Test passed |

The native manifest declares `open-telemetry` as a companion. Keeping explicit
companion setup also handles the existing chart's per-cluster Kubernetes
configuration. The three old SUSE AI Groovy synchronizations are not present in
this package; `stackpack-sync-status` enumerates and describes actual sync IDs.

The migration defaults to the server's upgrade API. A separate local deployment
record reports a successful 2.0.0 → 3.0.1 upgrade on Observability 2.11.1, but it
does not prove 2.2.0 → 3.0.0 and is not counted as this task's verification.
If the target backend rejects the schema transition, inspect its error and
preserve/export local customizations before choosing a controlled reinstall:

```bash
# Set the same authentication/STS_CONTEXT used by setup. Save settings first.
sts --context "$STS_CONTEXT" settings describe \
  --namespace urn:stackpack:suse-ai --file suse-ai-settings-before.sty
# Keep this export private; do not blindly reapply old schema settings to v2.
UNINSTALL=true bash init.sh
KUBERNETES_CLUSTERS=cluster-a,cluster-b bash init.sh
```

This existing uninstall/install path waits for complete removal and installs
the exact version from the archive. It is intentionally a separate operation,
not a fallback for an authentication, network, or arbitrary provisioning error.
It removes the old instance and its StackPack-owned settings/contributions.
Expect loss of unlocked StackPack customizations, old monitor overrides, saved
links tied to removed IDs, and continuity of 2.x synthetic component identities.
Native service/instance views compose with OpenTelemetry; the old synthetic
product/model identities are not migrated by this script. `overwrite` also
replaces unlocked settings during normal upgrade. The script issues no
telemetry-storage deletion command. Exact retention/history effects still need
verification on the target backend.

`CLEANUP_LEGACY=true` remains an explicit maintenance mode for the old “GenAI
Observability” menu and autosync instances with both `sts_instance_type=suse-ai`
and a selected cluster URL. It no longer matches unrelated autosync instances
by URL alone. It is not run for a fresh install or normal 2.x migration; owned
2.x resources should be removed through StackPack provisioning/deprovisioning.

## Verification and remaining live gate

Local checks passed: 67 native tests (12 opt-in backend tests skipped), 15
release tests, server validation of 93 nodes and rejection of the invalid CEL
control, shellcheck and Bash syntax. The complete suite and final focused installer logs are
`/tmp/suse-ai-release-tests-final.log`, `/tmp/suse-ai-release-init-final.log`
and `/tmp/suse-ai-release-validate.log`.
The HTTP-fixture test uses the installed CLI 3.9.2, not a replacement executable;
the other installer tests inject CLI failures and state transitions.

The requested `local-demo-20261026` context refuses connections at
`127.0.0.1:18080`. Its saved kubeconfig cannot reach `suse-rancher.demo:443`.
Newer deployment records identify `local-demo-20261030` as a different backend
already containing 3.0.1; its saved kubeconfig also times out. Both resolve the
Rancher endpoint to `35.95.71.90`. List and describe requests were attempted,
but no live `errorDetails` or rendered AI views could be read. No StackPack
was uploaded or installed by this task. A question about using the replacement
demo is pending; the explicit October 26 target has not been silently replaced.

After access is restored, capture the actual catalog, installed settings and
every topology-sync description before testing. Use CLI 3.9.2 and the exact
release archive for fresh install, a second invocation, and installation of
the unmodified old 2.2.0 package followed by the new installer. Upload each
version only once, reusing catalog entries for later scenarios. Preserve
available newer versions: the installer will refuse an unexpected
`nextVersion`; do not delete catalog versions merely to force a test through.
An isolated test backend/catalog may be necessary if 3.0.1 is offered instead.

For each scenario, save `sts stackpack list`, `list-instances`,
`sts topology-sync list`, and `describe --id <nodeId>` for every returned sync.
Compare active `errorDetails` with the baseline, separately from cumulative
counters. Check the native inventories, component highlights and charts through
an authenticated browser session; API/query checks alone are not proof that
the views render. The requested live acceptance gate is still open.

## IBS and chart handoff

- Fetch the intended public release tag, use `scripts/package-stackpack.sh`,
  verify `SHA256SUMS`, and install the archive at `/mnt/suse-ai.sts` with this
  `init.sh`. The old `zip ... stackpack.conf provisioning resources` recipe
  cannot build native v2. Workflows, IBS and container recipes need their
  separate owners' updates; this task does not modify them.
- Runtime dependencies: CLI 3.9.2, Bash, jq, unzip, sed, grep and GNU coreutils
  (`sort -V`, sleep). `STS_EXPERIMENTAL_STACKPACKS` is not required by setup.
- Keep `STACKSTATE_API_URL`, `STACKSTATE_TOKEN`, `STACKSTATE_TOKEN_TYPE`,
  `KUBERNETES_CLUSTERS` and TLS/CA mounts. `STS_CONTEXT` is an optional local-test
  alternative to explicit authentication variables; the container need not use it.
- The chart must rerun its setup Job on extension upgrades, wait for successful
  completion, and allow the default 300-second CLI operation timeout. Do not
  hide a nonzero installer exit. Keep installation singleton per backend to
  avoid racing concurrent uploads or installs.
- Do not automatically enable `CLEANUP_LEGACY` for v3. The native StackPack needs
  native OTel telemetry and compatible backend mapping/presentation support;
  installing it does not reconfigure the Collector. The unchanged legacy
  `integrations/otel-collector` examples target 2.x; use the imported native
  examples or the separately released compatible Collector profiles.

No tag, push or PR is performed without the user's confirmation.
