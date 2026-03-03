# StackState Groovy Script API Documentation

This document describes the StackState-specific Groovy API available for different types of scripts within StackPacks.

## 1. Provisioning Script API
Available in Groovy classes extending `com.stackstate.stackpack.ProvisioningScript`.

### `ProvisioningContext`
Accessed via `context()`, `stackPack()`, `instance()`, `sts()`, or `env()`.

#### `StackPackData` (`stackPack()`)
- `String name`: The name of the StackPack.
- `String displayName`: The display name.
- `Version version`: The version of the StackPack.
- `String scriptsDirectory`: Path to the scripts directory.
- `ProvisioningIO importSnapshot(String templateFile)`: Imports a template.
- `ProvisioningIO importSnapshot(String templateFile, Map params)`: Imports a template with parameters.

#### `InstanceData` (`instance()`)
- `String id`: The unique identifier of the StackPack instance.
- `ProvisioningIO importSnapshot(String templateFile)`: Imports an instance-specific template.
- `ProvisioningIO importSnapshot(String templateFile, Map params)`: Imports with parameters.

#### `Sts` (`sts()`)
- `void onDataReceived(String topic, Closure callback)`: Triggers the callback when data arrives on the specified topic.
- `void provisioningComplete()`: Marks the instance provisioning as successful.
- `ProvisioningIO fail(String errorMessage)`: Terminates provisioning with an error.
- `String createTopologyTopicName(String sourceType, String sourceId)`: Generates a standard topic name.
- `ProvisioningScriptLog log`: Logger with `info`, `debug`, `warning`, and `error` methods.

#### `Env` (`env()`)
- `ProcessResult execute(String command, String directory, Map env)`: Executes a shell command.
  - `ProcessResult` contains: `int exitCode`, `String stdOut`, `String stdErr`.

---

## 2. General Script API (Global Bindings)
Injected into Topology Mappers, Check Functions, and Propagation Functions.

### Global Bindings
| Binding | Description |
| :--- | :--- |
| `Sts` | Utility functions for data transformation. |
| `K8sQuantity` | Kubernetes quantity parser and formatter. |
| `runStates` | Constants for component run states. |
| `memory` | A `ConcurrentHashMap` for state persistence between script runs. |
| `context` | The execution context, providing access to `log()`. |

### `Sts` (StsApi)
- `createId(String externalId, String type)`: Creates a topology ID.
- `createId(String externalId, Set identifiers, String type)`: Creates an ID with multiple identifiers.
- `String ipToCanonical(String ip)`: Canonicalizes IP addresses (e.g., brackets for IPv6).
- `String portToCanonical(Object port)`: Canonicalizes port numbers to String.

### `K8sQuantity`
- `parse(String quantity)`: Returns a builder with the following methods:
  - `formatMillicores()`: Returns CPU in millicores as String.
  - `formatKi()`, `formatMi()`, `formatGi()`, `formatTi()`: Returns memory in the specified unit as String.

### `runStates` (RunStateApi)
Constants: `UNKNOWN`, `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, `DEPLOYED`, `DEPLOYING`.

### Health States
Constants: `CLEAR`, `DEVIATING`, `CRITICAL`, `UNKNOWN`, `DISABLED`, `FLAPPING`.

---

## 3. Common Monitor Helper Functions
Many StackPacks include shared Groovy scripts for telemetry and topology health.

### Telemetry Helpers (`Telemetry.groovy`)
- `telemetryHealthResponse(metric, health, urnTemplate, ...)`: Creates a `MonitorHealthState` object for telemetry-based monitors.
- `displayPromqlTimeSeries(name, timeSeriesId, query, alias)`: Creates a `DisplayTimeSeries` object for showing graphs in the UI.

### Topology Helpers (`Topology.groovy`)
- `topologyHealthResponse(topology, health, message, title, ...)`: Creates a `MonitorHealthState` object for topology-based monitors.
