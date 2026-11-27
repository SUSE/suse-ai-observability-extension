# DCGM metric compatibility

SUSE AI uses the metric families exposed by NVIDIA DCGM Exporter. Exporter 4.9.0 changed several default metric names and units. The GPU views in this change read either family. The published SUSE AI StackPack 3.0.0 uses the legacy names for GPU table utilization, framebuffer memory and the fleet dashboard's cluster selector. [DCGM Exporter 4.9.0 release notes](https://github.com/NVIDIA/dcgm-exporter/releases/tag/4.9.0)

## GPU Operator defaults

| GPU Operator chart | Default DCGM Exporter image tag | Metric format |
| --- | --- | --- |
| 26.7.2 | `4.6.1-4.8.4-distroless` (DCGM 4.6.1, exporter 4.8.4) | Utilization in percent, framebuffer memory in MiB |
| 26.7.3 | `4.7.0-4.9.0-distroless` (DCGM 4.7.0, exporter 4.9.0) | Utilization as a 0–1 ratio, framebuffer memory in bytes |

The chart can override the exporter image through `dcgmExporter.version`. To check an installation, inspect the running DaemonSet and confirm which metric names appear in Metrics Explorer. Use the namespace and DaemonSet name from your installation. [26.7.2 chart defaults](https://github.com/NVIDIA/gpu-operator/blob/v26.7.2/deployments/gpu-operator/values.yaml) · [26.7.3 chart defaults](https://github.com/NVIDIA/gpu-operator/blob/v26.7.3/deployments/gpu-operator/values.yaml)

```sh
kubectl -n gpu-operator get daemonset nvidia-dcgm-exporter \
  -o jsonpath='{range .spec.template.spec.containers[*]}{.image}{"\n"}{end}'
```

## Fields and units

| Purpose | Legacy field | DCGM 4.7 field | Normalization to the chart unit |
| --- | --- | --- | --- |
| GPU utilization | `DCGM_FI_DEV_GPU_UTIL` (%) | `DCGM_FI_DEV_GPU_UTIL_RATIO` (0–1) | `100 × ratio` |
| GPU temperature | `DCGM_FI_DEV_GPU_TEMP` (°C) | `DCGM_FI_DEV_GPU_TEMP_CELSIUS` (°C) | none |
| Board power | `DCGM_FI_DEV_POWER_USAGE` (W) | `DCGM_FI_DEV_BOARD_POWER_WATTS` (W) | none |
| Framebuffer used | `DCGM_FI_DEV_FB_USED` (MiB) | `DCGM_FI_DEV_FB_USED_BYTES` (bytes) | `1048576 × MiB` |
| Framebuffer free | `DCGM_FI_DEV_FB_FREE` (MiB) | `DCGM_FI_DEV_FB_FREE_BYTES` (bytes) | `1048576 × MiB` |
| SM clock | `DCGM_FI_DEV_SM_CLOCK` (MHz) | `DCGM_FI_DEV_SM_CLOCK_HERTZ` (Hz) | `1000000 × MHz` |
| Tensor activity | `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` (0–1) | `DCGM_FI_PROF_TENSOR_UTIL_RATIO` (0–1) | none |
| Last XID | `DCGM_FI_DEV_XID_ERRORS` | `DCGM_FI_DEV_XID_ERROR` | none |
| Driver version label | `DCGM_FI_DRIVER_VERSION` | `DCGM_FI_SYSTEM_DRIVER_VERSION` | Label only |

During an upgrade, the old and new driver-version labels can keep two series visible for the same device. Queries group each family by the device or workload identity before selecting the renamed family when present. A current utilization of zero therefore takes precedence over an older positive sample. An unavailable sensor yields no reading.

## GPU identity in each view

- **Device discovery** accepts either utilization metric. A cluster and GPU UUID identify the device. The mapping also requires a node name to create the node relation. Samples with a MIG instance ID or profile are excluded.
- **The fleet dashboard** groups physical GPU readings by cluster, node and UUID. Repeated workload and scrape labels contribute one reading per device.
- **The node table** accepts observations identified by GPU index, UUID, or both. It groups the physical device readings into a single utilization or memory value for each node. Index-only exporters can populate this table.
- **Pod views** use the workload's namespace and pod name reported by DCGM. Their device grouping retains the available GPU index and UUID. The vGPU charts also retain vGPU and container labels.

## Regression coverage

The GPU workflow evaluates the shipped PromQL expressions against legacy, renamed and overlapping series, including the driver-label transition, real zeros, unavailable sensors and MIG slices. Mapping tests check GPU identity and allocation to a workload pod. [GPU regression workflow](../.github/workflows/gpu-metrics.yml)
