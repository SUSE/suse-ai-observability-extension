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
`.sts`, `target/`, caches and other untracked artifacts behind. The validation
workflow now runs the native Taskfile validator. The obsolete root Dockerfile
and setup-image `build`/`push` tasks were removed during review. The independent
Ollama exporter image tasks remain available.

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

For demo prereleases, use `task demo-deploy` with its explicit localhost URL,
token file and version ledger. On 2026-11-06 the demo catalog ordered `dev.10`
below `dev.9` and offered no upgrade. The task now chooses a suffix above both
numeric and lexical order, so version numbers can jump (for example `dev.9` to
`dev.90`). Uploaded versions stay consumed, including a version the server did
not offer for upgrade. The successful dev.90 upgrade used overwrite and retained
the instance; [evidence and limits](V3_UX_REVIEW_20261106.md#deployment-and-verification).

Authentication defaults to a service token. For a user API token, set
`DEMO_TOKEN_TYPE=api`; the task uses `sts --api-token` and carries that choice
into its verification step. For a standalone `task demo-inspect`, set
`SPIKE_TOKEN_TYPE=api`. Inspection sends the matching `X-API-Token`
header for HTTP snapshots. Both tasks read credentials from their token-file
argument; keep that file private and outside the repository.

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
| Fresh | Ensure `kubernetes-v2` per cluster and `open-telemetry`; upload once; install exact bundled version with wait; read back status/version | Live 3.0.0 instance `73808763791700`, `INSTALLED`; new Kubernetes companion accepted at `WAITING_FOR_DATA` |
| Successful re-run | Read installed state; no upload, install, upgrade or deletion | Live fresh and post-upgrade re-runs made only read calls; instance IDs and update timestamps unchanged |
| 2.2.0 → 3.0.0 | Upload if absent; verify server's `nextVersion` equals bundled version; upgrade with `--unlocked-strategy overwrite --wait`; verify final state | Live old-schema instance `93492368154496` upgraded to native 3.0.0 with the same ID; no reinstall |
| Newer installed version | Fail before changing companions or AI | Test passed |
| Different server upgrade target | Fail instead of installing an unintended version | Test passed |
| Read/auth/upload/upgrade failure | Fail; no claim that upload failure means “already exists”; no automatic uninstall | Failure-injection tests passed |
| Uninstall/re-run uninstall | Uninstall AI instances, wait until absent; second run makes no changes | Test passed |

The native manifest declares `open-telemetry` as a companion. Keeping explicit
companion setup also handles the existing chart's per-cluster Kubernetes
configuration. The three old SUSE AI Groovy synchronizations are not present in
this package; `stackpack-sync-status` enumerates and describes actual sync IDs.

CLI 3.9.2's `install --wait` waits for `INSTALLED` and timed out after five
minutes for a newly provisioned Kubernetes companion at `WAITING_FOR_DATA`.
The installer now submits companion installation without that flag and polls
until `INSTALLED` or `WAITING_FOR_DATA`, failing on an error or timeout. SUSE AI
itself still requires `INSTALLED`. The real-CLI regression fixture now returns
`WAITING_FOR_DATA` for Kubernetes, exercising this behavior without telemetry.

The server's normal upgrade API successfully migrated 2.2.0 to 3.0.0 on the
user-provided November 2 Observability 2.11.1 environment with CLI 3.9.2. It
preserved the instance ID and removed the three old SUSE AI synchronizations.
Neither experimental StackPack environment variable was set for that upgrade.
No schema-specific flag or destructive reinstall was needed.

Before upgrading a customized 2.x installation, export its settings because
`overwrite` replaces unlocked settings. If a different backend rejects the
transition, inspect its error before choosing this explicit recovery path:

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
telemetry-storage deletion command. The November 2 backend had no AI telemetry;
historical data continuity and customized override migration were not tested.

`CLEANUP_LEGACY=true` remains an explicit maintenance mode for the old “GenAI
Observability” menu and autosync instances with both `sts_instance_type=suse-ai`
and a selected cluster URL. It no longer matches unrelated autosync instances
by URL alone. It is not run for a fresh install or normal 2.x migration; owned
2.x resources should be removed through StackPack provisioning/deprovisioning.

## Verification

Local checks passed: 67 native tests (12 opt-in backend tests skipped), 15
release tests, server validation of 93 nodes and rejection of the invalid CEL
control, shellcheck and Bash syntax. The complete suite and final focused installer logs are
`/tmp/suse-ai-release-tests-final.log`, `/tmp/suse-ai-release-init-final.log`
and `/tmp/suse-ai-release-validate.log`.
The HTTP-fixture test uses the installed CLI 3.9.2, not a replacement executable;
the other installer tests inject CLI failures and state transitions.

On October 30 the requested October 26 context and the newer October 30
kubeconfig were unreachable. The historical failed checks remain recorded in
`CERTAINS.md`. On November 2 the user supplied a replacement kubeconfig and
credentials, enabling the following live checks. A private CLI configuration
named `local-demo-20261102` was used without changing the user's global context.

The replacement backend initially had no SUSE AI catalog entry or instance.
The old 2.2.0 archive came from the unmodified package at this repository's
base commit `1fc9319` (100 files). Both 2.2.0 and the exact reproducible 3.0.0
archive were uploaded once. The sequence was fresh 3.0.0 install, no-op re-run,
remove that test instance, install 2.2.0, upgrade through the new `init.sh`,
and another no-op re-run. No catalog versions were deleted or replaced.

`sts stackpack list`, topology-sync list and every returned sync description
were saved for baseline, fresh, re-run, legacy, upgrade and post-upgrade
re-run. Once SUSE AI existed in the catalog, snapshots also saved
`list-instances` and `list-versions`. All observed syncs were `Running`, with
cumulative `errors: 0` and `errorDetails: []`. The final syncs are:

| Synchronization | Node ID |
| --- | --- |
| Agent | `263987850596316` |
| Kubernetes - local | `232505802755175` |
| Kubernetes - suse-ai | `271228421880615` |

The legacy install additionally had `SUSE AI` (`174686616215848`), `SUSE AI
Products` (`234150997558210`) and `SUSE AI Topology` (`82864948584708`), all
without errors. The normal upgrade removed them, without `CLEANUP_LEGACY`.
The existing OpenTelemetry instance and the existing `suse-ai` Kubernetes
companion were retained. A `local` Kubernetes companion was added by the test.

The live test exposed and verified the companion readiness fix described
above. After that fix all 15 release regressions passed, as did shellcheck
and Bash syntax checks; the `.sts` hash is unchanged. Evidence is stored outside
Git in `/home/thbertoldi/suse/qa/extension-v3-setup-20261102-29gb77gq/`, including
scenario logs, sanitized CLI argument audits, JSON snapshots and private
settings exports. Credentials and browser sessions are not repository files.

An authenticated Chromium session rendered all six SUSE AI menu inventories:
Overview, Applications & agents, Models, Inference, Data services and GPU
infrastructure. Each overview API returned HTTP 200, with no page errors or
failed requests; screenshots and DOM text were saved as `upgrade-view-*.png`
and `upgrade-view-*.json`. The menu and each screenshot were visually checked.
The inventories had zero components, so these checks establish rendering of
the native definitions and empty states, not populated highlights or charts.
The opt-in telemetry/backend tests remain unrun on this empty environment.

Browser access used the configured `https://suse-observability` origin through
an ingress port-forward. The initial localhost browser attempt returned HTTP
403 with `Allowed Origin header values: https://suse-observability`; using the
configured origin resolved it without changing server security settings.
CLI token access through the router port-forward worked throughout.

## IBS and chart handoff

- Fetch the intended public release tag, use `scripts/package-stackpack.sh`,
  verify `SHA256SUMS`, and install the archive at `/mnt/suse-ai.sts` with this
  `init.sh`. The old `zip ... stackpack.conf provisioning resources` recipe
  cannot build native v2. The obsolete root Dockerfile has been removed;
  packaging maintained outside this repository still needs the native layout.
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

## Ollama model inventory and table cleanup for 3.0.0

The combined release adds available Ollama models and focused native/observed
dependency tables. At the user's request, the StackPack and exporter release
target is 3.0.0. Earlier validation used 3.0.1 and temporary review versions;
those evidence labels remain unchanged. `init.sh` needs no change and continues
to upgrade with `--unlocked-strategy overwrite`. Never reupload a version after
changing its package bytes. The design, compatibility limits, validation record
and monitoring-guide handoff are in
[OLLAMA_MODEL_INVENTORY.md](OLLAMA_MODEL_INVENTORY.md).

The earlier import hashes and 3.0.0 release evidence above describe the earlier
build and remain historical records. This change adds Ollama mappings and
presentations and revises the overview tables; it does not change ComponentType
icons, legacy Groovy code or the vLLM component/relation identity contract.
The current package hash and version-change checks are in
[the table review report](OVERVIEW_TABLES_3.0.1.md#release-target-changed-to-300).
