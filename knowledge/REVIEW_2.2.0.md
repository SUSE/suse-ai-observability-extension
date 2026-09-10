# Version 2.2.0 review — 2026-09-09

This document records the original 2.2.0 tag at commit `f444ae4` and its
reproduced defects. The subsequent working-tree fixes were validated under
temporary version metadata `2.2.10`; on 2026-09-10, the user designated the
corrected source as official version `2.2.0` and stated that they would recreate
the tag. This review's findings and recommendation apply to the original
commit. Fix validation is tracked in [REGRESSION_TESTS.md](REGRESSION_TESTS.md)
and CERTAINS sections 17–18.

**Original review recommendation: request changes before approving commit `f444ae4` for production.** The review found one high-priority regression and six additional correctness defects. Static validation passes, but local runtime and query probes reproduce failures that it does not cover.

The comparison is remote tag `v2.1.0` at `5274216565ee5925d108c5acca20bfb8398755df` against remote tag `v2.2.0` at `f444ae428d711ce76eb49f6be0be0ed5b93a2d74`. The latter is also the pulled `main`. The change spans 51 files. Collector changes below affect customers adopting the new Collector examples; installing only the StackPack does not apply those YAML files.

**1. [P1] The new Kubeflow trace branch bypasses sampling for every workload.**

Location: [otel-values.yaml:720](../integrations/otel-collector/otel-values.yaml#L720), also [otel-collector-operator.yaml:708](../integrations/otel-collector/otel-collector-operator.yaml#L708).

`traces/kubeflow-relations` receives the entire forwarded trace stream and exports it through `otlp`. Its transforms conditionally edit attributes; they do not filter non-Kubeflow spans. This branch has no sampler. Consequently, ordinary HTTP workloads now export spans even when `traces/sampling` rejects them. Sampled spans also have another export path with the same trace/span IDs, although backend deduplication behavior was not tested.

Reproduction: submit one ordinary, non-GenAI trace containing 600 short spans. With the same pinned Collector executable and the source sampling policies, both versions' samplers export zero spans. Version 2.1.0 exports zero through all tested backend branches; 2.2.0 exports all 600 through the new Kubeflow branch. The test changes backend exporters to local files and supplies Kubernetes metadata directly, leaving the branch transforms and sampling policy intact.

Fix direction: put the required Kubeflow annotation transforms on the original trace path before sampling. If an additional topology path is necessary, restrict its input and avoid exporting another unsampled copy of original traces to the trace backend.

**2. [P2] Application inference overwrites a known Kubernetes namespace.**

Location: [otel-values.yaml:560](../integrations/otel-collector/otel-values.yaml#L560), also the Operator example's `transform/infer-applications`.

The two new assignments use `service.namespace` or `SUSE_AI_NAMESPACE` without checking whether `k8s.namespace.name` already exists. An application outside the default SUSE AI namespace therefore acquires incorrect topology/metric labels when its SDK omits `service.namespace`. A logical service namespace can also differ from its Kubernetes namespace.

Reproduction: send a GenAI metric resource with `k8s.namespace.name=tenant-a`, a pod identity, and no `service.namespace`. With `SUSE_AI_NAMESPACE=suse-private-ai`, the actual inference pipeline preserves `tenant-a` in 2.1.0 and produces `suse-private-ai` in 2.2.0. Kubernetes enrichment was replaced by an already-enriched input fixture.

Fix direction: fill a missing Kubernetes namespace; preserve an existing one. Apply the guard to both examples.

**3. [P2] Model Registry monitors use an identifier absent from metrics-only discovery.**

Location: [Model Registry monitors:21](../stackpack/suse-ai/provisioning/templates/monitors/kubeflow-model-registry/monitor.sty#L21), repeated at lines 44 and 67; [product ID extractor:41](../stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy#L41).

The synthetic HTTP check tags the product as `ml-registry`. The product extractor therefore creates `urn:suse-ai:product:ml-registry:kubeflow-model-registry`, while all three monitors target `urn:suse-ai:product:inference-engine:kubeflow-model-registry`. With only the documented synthetic check, the target identifier is absent, preventing attachment to that discovered component.

A Groovy fixture using the check's resource tags confirms that the product's identifiers contain the canonical ML-registry URN and its prefixed OTel identity, but not the monitor's legacy URN. A separate legacy trace-inferred component can supply that alias and mask the problem in the demo. Live backend attachment was unavailable for this review.

Fix direction: target the canonical ML-registry identifier, which the topology extractor also preserves as an alias when it receives the legacy external ID. Keep the collector-emitted external ID for relation resolution.

**4. [P2] The Model Registry invalid-response expression cannot detect the failed check signal.**

Location: [Model Registry monitor:63](../stackpack/suse-ai/provisioning/templates/monitors/kubeflow-model-registry/monitor.sty#L63), also [its validation chart:71](../stackpack/suse-ai/provisioning/templates/metric-bindings/kubeflow-model-registry-metrics.sty#L71).

The expression is `1 - max(httpcheck_validation_passed{...})`. In Collector 0.156.0, a failed `contains` check produces a failed-validation datapoint; it does not produce a zero-valued passed-validation datapoint. This matches the [upstream scraper implementation](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.156.0/receiver/httpcheckreceiver/scraper.go).

Reproduction: a localhost endpoint returns HTTP 200 with `{"error":"wrong response body"}`. The actual configured receiver emits `httpcheck.validation.failed=1` and no passed sample. Importing that failure signal into a local VictoriaMetrics instance makes the shipped expression return an empty vector, rather than the positive value required to alert. A previous successful sample can instead keep the expression at zero while it remains eligible for lookback.

Fix direction: use the emitted failed-validation metric, and explicitly decide how absent checks should affect health. Correct the monitor and chart together. This is independent of the identifier defect above.

**5. [P2] KServe controller alerts include unrelated controllers.**

Location: [KServe monitor:18](../stackpack/suse-ai/provisioning/templates/monitors/kserve/monitor.sty#L18) and [line 64](../stackpack/suse-ai/provisioning/templates/monitors/kserve/monitor.sty#L64).

The reconcile-ratio and unfinished-work queries have no KServe selector. Both metric families are shared by Kubernetes controllers. The resulting global number is attached to the KServe component, unlike the corresponding metric bindings, which select `suse_ai_component_name="kserve"`.

Reproduction: fixture KServe counters contain only successful reconciliations and its unfinished-work gauge is zero. An unrelated operator contributes errors and a 120-second unfinished-work gauge. The exact shipped expressions return a 90.91% error ratio and 120 seconds, crossing both KServe thresholds. Unrelated successful activity can conversely dilute a real KServe error ratio.

Fix direction: scope every controller series to the KServe product before aggregation. Also verify the lag description: unfinished-work seconds accumulate across in-progress items and are not the age of the oldest item.

**6. [P2] Model Registry specialization hard-codes the namespace `kubeflow`.**

Location: [topology component mapper:18](../stackpack/suse-ai/provisioning/templates/sync/topology-sync-component-mapping-function.groovy#L18) and [line 28](../stackpack/suse-ai/provisioning/templates/sync/topology-sync-component-mapping-function.groovy#L28).

The new mapper removes every incoming Kubernetes namespace label and adds `k8s.namespace.name:kubeflow`. Both Collector examples expose `KUBEFLOW_NAMESPACE` as configurable, so the mapper disagrees with configurations that use another namespace.

Reproduction: executing the actual Groovy mapper with `k8s.namespace.name:ml-platform` removes that label and returns `k8s.namespace.name:kubeflow`; the cluster label remains unchanged. Version 2.1.0 had no such mapper. This defect is separate from application inference: it affects topology-exported Model Registry components.

Fix direction: carry the actual product namespace through discovery/mapping; do not replace it with a demo-specific constant. Retaining the topology exporter's generic SUSE AI namespace alone may also be insufficient to identify the registry's actual namespace.

**7. [P2] New pod vGPU bindings mix same-named pods across namespaces.**

Location: [common-metrics.sty:262](../stackpack/suse-ai/provisioning/templates/metric-bindings/common-metrics.sty#L262); the selectors at lines 241 and 283 have the same omission.

The selectors constrain node and pod name, but not pod namespace or cluster. For the container chart, `max by (container_name, gpu, vgpu)` then removes the namespace distinction. This can display another tenant's usage as the selected pod's usage. The newly added node bindings similarly omit cluster identity.

Reproduction: `tenant-a/worker-0` and `tenant-b/worker-0` run on `worker-1` with matching container/GPU/vGPU labels and report 10% and 90%. The exact container query for the first pod returns one 90% series. Both series are legitimate inputs under the dimensions documented in this change.

Fix direction: constrain the metric selector by the component's namespace and cluster before aggregation. Validate the actual component tag names and exporter labels when implementing this fix. Similar omissions exist in older GPU bindings; that older debt does not make the new bindings correct.

**Other release considerations**

The topology data source's expiration changes from five minutes to one day for its elements, not just Kubeflow relations. This is a deliberate behavior change with a topology-freshness tradeoff when updates stop. It should be documented as such; it is distinct from the Collector exporter's 15-minute retention and complete-snapshot removal behavior. Live expiry behavior was not reproduced, so this is not counted among the seven confirmed findings.

RC0 and the originally reviewed release share the embedded StackPack version `2.2.0`. RC0's archive matches its tag exactly but differs from the original final tag's two GPU metric-binding files. The review initially recommended a new follow-up version under the repository's no-reuse rule. The user's 2026-09-10 decision supersedes that release-number recommendation: the corrected source is designated official `2.2.0`. No upload or upgrade was attempted during this review.

The unresolved Milvus metric-binding reference ending in `vectordb-system-request-sucess-rate` is present in both 2.1.0 and 2.2.0. The unchanged setup/container publication paths also retain their existing limitations. These were not attributed to the 2.2.0 changes.

**Uncommitted CERTAINS assessment**

The original local diff contained seven fact bullets in two appended sections. Upstream independently appended a Collector verification section numbered 13 and added a vGPU fact earlier in the document. All content was preserved; the local sections are now 14 and 15. There are no unresolved Git conflicts.

| Local material | Assessment | Treatment |
| --- | --- | --- |
| RC0 tag, digest, CLI, archive and validation counts | Useful historical release provenance. Not acceptance evidence for final 2.2.0. | Retained, distinguished historical build commands from rechecked artifact properties, and recorded the final-tag mismatch. |
| Topology topic and older Collector defaults | Useful compatibility contract. `instance_url` alone does not make the full newer config compatible with 0.149.0. | Retained and bounded to checked tags; documented unsupported older keys. |
| Cluster name versus topology stream identity | Useful operational distinction that prevents topology stream mismatches. | Retained. |
| Retention across exporter flushes | Useful for diagnosing disappearing relations. It is separate from backend data-source expiration. | Retained and clarified. |
| “Current” Collector reference version | Useful only when tied to a specific extension revision. | Reworded as the 2.2.0 image pin, without asserting that 0.156.0 is the newest Collector. |

The original local file and patch are backed up in `/tmp/suse-ai-2.2.0-review-c12q7ou8/`; the dedicated Git stash `Preserve local CERTAINS before 2.2.0 review` is also retained. Existing untracked documents and tooling were preserved. At the end of the initial review, the changes covered documentation only and remained uncommitted; implementation and delivery are recorded in CERTAINS sections 17–19.

**Verification and limits**

| Check | Result |
| --- | --- |
| Remote baseline and release tag hashes | Verified with `git ls-remote`; `main` fast-forwarded to the release commit. |
| `task stackpack-validate` | Passed: 255 unique numeric IDs; zero Groovy errors, 27 warnings and 187 informational findings across five scripts. |
| STY structure/includes/identifiers | 46 files checked; expanded master parses with 269 unique node URNs; referenced include files exist. Handlebars helpers were substituted for this structural check. |
| Collector Helm example | Upstream chart 0.165.0 rendered successfully; its actual Collector config passed image 0.156.0 `validate`. |
| Collector Operator example | Extracted `spec.config` passed the same image's `validate`. No Operator deployment was performed. |
| Trace/metric runtime probes | Reproduced sampling bypass, namespace overwrite, and HTTP validation emission using the executable extracted from the pinned image. |
| Groovy fixtures | Reproduced registry namespace replacement and the monitor/product identifier mismatch. The fixture itself also passed Groovy lint with zero errors. |
| Query fixtures | Exact expressions evaluated in isolated VictoriaMetrics v1.151.0 reproduce both KServe false positives, the empty invalid-response result, and cross-namespace vGPU aggregation. |
| RC0 provenance | GHCR digest matches the preserved record; CLI 3.3.8 verified; ZIP integrity and all 100 packaged files match the RC tag; 249 unique numeric IDs. |
| Live SUSE Observability | Unavailable: default `localhost:8081` and alternate `127.0.0.1:8090` refused connections. `sts topology-sync list` and `sts topology-sync describe` were attempted. |

Collector validation used dummy environment values and a mounted placeholder ServiceAccount token. Runtime probes use local fixtures and file exporters; they do not exercise Kubernetes discovery, live backend ingestion, monitor attachment, STY schema/provisioning, or upgrade behavior. Existing historical live validations in CERTAINS were preserved, not represented as repeated by this review. No StackPack was uploaded or deployed.

The initial tag fetch also refused to overwrite divergent local `v1.0.1` and `v2.0.0` tags. Those tags were left untouched. Neither comparison tag was affected, and the remote `v2.0.0` commit's topology topic was separately checked for the compatibility note.

Probe scripts, input fixtures, generated Collector configs, CLI output and validation logs are in `/tmp/suse-ai-2.2.0-review-c12q7ou8/`. The probes are run through its Taskfile:

```bash
task -t /tmp/suse-ai-2.2.0-review-c12q7ou8/Taskfile.yaml trace-probe
task -t /tmp/suse-ai-2.2.0-review-c12q7ou8/Taskfile.yaml metric-probes
task -t /tmp/suse-ai-2.2.0-review-c12q7ou8/Taskfile.yaml groovy-probe
task -t /tmp/suse-ai-2.2.0-review-c12q7ou8/Taskfile.yaml query-probes
```
