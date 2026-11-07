# GPU recovery and topology comparison — 2026-11-06

The demo is installed at **3.0.0-dev.92**, instance `261989587621111`.
The supplied chameleon was deployed in dev.91; dev.92 adds the GPU columns and
automatic topology grouping. Both versions were uploaded once and installed with
`--unlocked-strategy overwrite`. The release source remains 3.0.0.

## Why GPU nodes disappeared

The downstream Kubernetes Agent used the demo's temporary bootstrap service
token, which expired at **15:35:54 UTC on November 6**. Agent logs recorded
`401 Unauthorized` and an expired-token response for both metrics and topology
intake. All four cluster nodes were Ready, and all four DCGM devices continued
to report metrics through the Collector. The native Kubernetes node components
were absent, so the GPU-node table had no matching rows.

The Agent now uses a dedicated ingestion service token with no expiration set.
Its subject has `update-metrics` on `system` and `update-scoped-permissions` on
the `suse-ai` cluster. This follows the documented
[service-token ingestion procedure](https://documentation.suse.com/en-us/cloudnative/suse-observability/latest/en/use/security/k8s-service-tokens.html).
No administrator role was assigned to that token.

Agent Helm release revision 3 retains chart **1.7.19**, application **3.78.2**.
The reviewed manifest difference contains only the ingestion-secret value and
Agent rollout annotations. The internal cluster-Agent authentication token was
preserved. Values, manifests, workloads and the original secret were backed up
privately before the upgrade. Fresh cluster-Agent logs contain successful
topology checks and no authentication failures; all four native GPU nodes and
their table rows have returned.

## GPU table comparison

The previous-field names below are the user's supplied inventory. The dev.91
column state is captured after ingestion recovery, before the presentation change.
The final table has **17 columns**, including the node link. Health, Node and GPU
model remain fixed during horizontal scrolling.

| Previous field | dev.91 table | dev.92 table |
| --- | --- | --- |
| Status | Health | Health |
| GPUs | GPUs | GPUs; physical count, excluding scheduling replicas |
| Model | GPU model | GPU model |
| Family | Available in component details only | **GPU family restored to table** |
| Node OS | Available in component details only | **Node OS restored to table** |
| OS Version | Available in component details only | **OS version restored to table** |
| CUDA Version | Available in component details only | **CUDA version restored to table** |
| Driver Version | Available in component details only | **Driver version restored to table** |
| GPU Memory | Memory / GPU | Memory / GPU; capacity per device |
| GPU Temperature Average | Temperature | GPU temperature average |
| GPU Power Total | Power | GPU power total |
| GPU Utilization | GPU utilization | GPU utilization |
| GPU Memory Utilization | Memory used | GPU memory utilization |
| CPU Usage | Host CPU usage | Host CPU usage |
| Usable Memory | Usable host memory | Usable host memory |
| Cluster | Cluster link | Cluster link |

All four nodes report the restored values: Turing, SLES 15.7, CUDA 13.4 and
driver 615.71.09. Each value was compared with the live Kubernetes node labels.
All **24** bound table metric queries returned finite samples, including the
Agent's host CPU and usable-memory measurements. CPU, host memory and Cluster
are on the right of the wide table; scroll horizontally to see them.

## Topology comparison

The original AI view collapsed ten services, including Ollama, into a single
`otel service group (10)`. Its fixed grouping configuration differed from Open
Telemetry's automatic grouping. A read-only comparison used the same AI query
and changed one option at a time: enabling `autoGrouping` retained all 21 selected
components and produced zero collapsed groups. Copying every native option also
added a connected component, so that broader change was not needed.

| Setting or result | AI before | AI after | Open Telemetry Services |
| --- | --- | --- | --- |
| `groupingEnabled` | true | true | true |
| `minimumGroupSize` | 8 | 8 | 8 |
| `autoGrouping` | false | **true** | true |
| `groupedByDomains` | false | false | true |
| `connectedComponents` | false | false | true |
| Components in captured topology | 21 | 21 | 19 |
| Collapsed groups in captured topology | 1, containing 10 services | **0** | 0 |

The AI scope remains native services and served models. Replicas and model usage
stay in component drilldowns. Automatic grouping can still group larger future
topologies; the zero-group result is verified for this live dataset.

The model-to-engine relation and health propagation were not changed. Models
still appear above their serving engines; this iteration fixes collapsed groups,
not that separate layout limitation.

The subsequent [direct model-health change](V3_MODEL_HEALTH_20261106.md) reverses
the serving edges and addresses that layout limitation in dev.94.

## Other presentation and component differences

| Area | Change in this iteration |
| --- | --- |
| StackPack menu | Exact user-supplied chameleon PNG embedded in the served SVG; 16×16 intrinsic size, 18×18 in the menu |
| Submenus | Same six: Overview, Applications & agents, Models, Inference, Data services, GPUs |
| Native Open Telemetry pages | Services and Service instances table metadata unchanged; Services topology still has zero collapsed groups |
| Native GPU nodes | Four recovered after fixing ingestion; five descriptive table columns added |
| Physical GPU components | Four present, with real metrics; no new device-bound health monitor added |
| Served models and agent | Existing hosting relations and health behavior retained |
| Monitors | All 68 current monitor identifiers and numeric IDs preserved |
| Demo tooling | API-token and service-token modes supported by deployment and inspection tasks |

The earlier component/menu redesign comparisons remain in
[the grouping report](V3_GROUPING_COMPARISON_20261106.md),
[the health-table report](V3_HEALTH_TABLES_20261106.md) and
[the adversarial UX review](V3_UX_REVIEW_20261106.md).

## Validation and remaining backend errors

- Native tests: **107**, with 18 opt-in checks skipped and no failures.
- Release/deployment tests: **24 passed**.
- Native validation: **117 nodes accepted**; invalid-CEL control rejected.
- All **173** staged package files match the source except the intentional dev
  manifest version. The menu PNG matches the supplied image byte for byte.
- Both topology synchronizations are Running. Agent reports 10 errors with 10
  active details. After ingestion resumed, Kubernetes reports 26 errors with 11
  active details: duplicate external-volume/secret relations and a multiple-host
  snapshot warning. These were not cleared; no clean-backend claim is made.
- All **19 observed SUSE AI mappings** have zero mapping errors. Two dormant
  database mappings still return 404 because they have no observations.

Evidence root:
`/home/thbertoldi/suse/qa/demo-v3-menu-icon-s_bvp5h_/resume/`.
Key files: `final/audit.json`, `final/gpu-table-metrics.json`,
`final/sync-details-rechecked.json`, `gpu-diagnosis/helm-rendered-diff-paths.json`
and the before/after topology WebSocket snapshots. Secrets and raw backups are
outside Git.

Screenshots:

- [AI topology before](/home/thbertoldi/suse/qa/demo-v3-menu-icon-s_bvp5h_/resume/topology-before-auth/suse-ai.png)
  / [after](/home/thbertoldi/suse/qa/demo-v3-menu-icon-s_bvp5h_/resume/topology-after/suse-ai.png).
- [Open Telemetry topology before](/home/thbertoldi/suse/qa/demo-v3-menu-icon-s_bvp5h_/resume/topology-before-auth/opentelemetry.png)
  / [after](/home/thbertoldi/suse/qa/demo-v3-menu-icon-s_bvp5h_/resume/topology-after/opentelemetry.png).
- [GPU table](/home/thbertoldi/suse/qa/demo-v3-menu-icon-s_bvp5h_/resume/gpu-final/gpu-table.png)
  / [right-hand columns](/home/thbertoldi/suse/qa/demo-v3-menu-icon-s_bvp5h_/resume/gpu-final/gpu-table-right.png).
- [Supplied menu icon in the demo](/home/thbertoldi/suse/qa/demo-v3-menu-icon-s_bvp5h_/resume/gpu-final/menu.png).
