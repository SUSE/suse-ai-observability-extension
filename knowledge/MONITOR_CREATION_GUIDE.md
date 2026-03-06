# Comprehensive Guide to Monitor Creation in StackState StackPacks

## Table of Contents

1. [Introduction](#introduction)
2. [Monitor Fundamentals](#monitor-fundamentals)
3. [Monitor Structure and Fields](#monitor-structure-and-fields)
4. [Monitor Function Types](#monitor-function-types)
5. [Component Attachment via URN Templates](#component-attachment-via-urn-templates)
6. [Metric Queries and PromQL](#metric-queries-and-promql)
7. [Creating a New Monitor - Step by Step](#creating-a-new-monitor---step-by-step)
8. [Remediation Hints](#remediation-hints)
9. [Best Practices](#best-practices)
10. [Advanced Patterns](#advanced-patterns)
11. [Monitor Provisioning](#monitor-provisioning)
12. [Testing Monitors](#testing-monitors)

---

## Introduction

This guide provides a comprehensive overview of how monitors are created in StackState StackPacks. A **monitor** is a declarative configuration that defines:
- What condition should be evaluated
- How to evaluate it (threshold, anomaly detection, etc.)
- Which component(s) to attach to
- What to do when the condition is met (health state change, remediation hints)

Monitors are the core mechanism for transforming raw telemetry data (metrics, traces, logs) into actionable health information for your components.

### What You Will Learn

By the end of this guide, you will understand:
- The complete structure of a monitor definition
- The different types of monitor functions available
- How monitors attach to components via URN templates
- How to write PromQL queries for monitors
- How to create custom monitor functions using Groovy
- Best practices for monitor creation

---

## Monitor Fundamentals

### What is a Monitor?

A monitor is a StackState configuration object that evaluates telemetry data against defined conditions and associates the resulting health state with one or more components. Monitors are:

- **Declarative**: Defined as YAML-like objects in `.sty` template files
- **Attached to Components**: Connected via URN (Uniform Resource Name) templates
- **Interval-based**: Run at configurable intervals (typically 30-60 seconds)
- **Stateful**: Return health states (CLEAR, DEVIATING, CRITICAL, UNKNOWN)

### Monitor vs. Monitor Function

It is important to distinguish between **Monitors** and **Monitor Functions**:

| Concept | Description |
|---------|-------------|
| **Monitor** | The specific monitoring rule/config that attaches to components. Example: "Monitor CPU usage > 80% for pods" |
| **Monitor Function** | The underlying implementation/logic that evaluates the condition. Example: "Threshold monitor function" |

A monitor references a monitor function via its `function` field. The monitor function contains the actual evaluation logic.

---

## Monitor Structure and Fields

### Complete Monitor Definition Structure

Here is the complete structure of a monitor definition with all available fields:

```yaml
- _type: Monitor
  name: "Display name for the monitor"
  identifier: "urn:stackpack:<stackpack-name>:shared:monitor:<unique-id>"
  description: |
    Detailed description of what this monitor does
    Can span multiple lines
  status: ENABLED  # or DISABLED
  tags:
    - tag1
    - tag2
  function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
  intervalSeconds: 30
  arguments:
    # Function-specific arguments (see Monitor Function Types section)
    comparator: GT
    failureState: DEVIATING
    threshold: 80.0
    metric:
      query: "promql_query_here"
      aliasTemplate: "Display name for metric"
      unit: percent  # short, ms, percent, cps, bytes, etc.
    titleTemplate: "Title shown in UI (${variable})"
    urnTemplate: "urn:component:type/${identifier}"
  remediationHint: "{{ include './path/to/remediation-hint.md.hbs' 'identity' }}"
```

### Field Reference

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `_type` | Yes | Always set to `Monitor` | `Monitor` |
| `name` | Yes | Human-readable display name | `CPU usage threshold` |
| `identifier` | Yes | Unique URN identifier | `urn:stackpack:kubernetes:shared:monitor:pod-cpu-usage` |
| `description` | Yes | Detailed description | Monitors CPU usage... |
| `status` | Yes | Enable/disable state | `ENABLED` or `DISABLED` |
| `tags` | No | Categorization tags | `["kubernetes", "cpu"]` |
| `function` | Yes | Monitor function reference | `{{ get "urn:stackpack:common:monitor-function:threshold" }}` |
| `intervalSeconds` | Yes | Evaluation interval | `30`, `60`, `300` |
| `arguments` | Yes | Function-specific configuration | See below |
| `remediationHint` | No | Path to remediation template | `{{ include "./templates/..." }}` |

### Arguments by Monitor Function Type

#### Threshold Monitor Function

```yaml
arguments:
  comparator: GT           # GT, GTE, LT, LTE
  failureState: DEVIATING   # CRITICAL, DEVIATING
  threshold: 80.0          # Numeric threshold
  metric:
    query: "promql_query"
    aliasTemplate: "Metric display name"
    unit: percent
  titleTemplate: "Title (${label})"
  urnTemplate: "urn:component:${identifier}"
```

#### Topological Threshold Monitor Function

```yaml
arguments:
  comparator: GT
  failureState: DEVIATING
  threshold: 5000
  metric:
    query: "histogram_quantile(0.95, sum by(...) (rate(...)))"
    aliasTemplate: "Span duration 95th percentile"
    unit: ms
  titleTemplate: "Span duration"
  urnTemplate: "urn:opentelemetry:namespace/${service_namespace}:service/${service_name}"
```

#### Anomaly Detection Monitor Function (AAD)

```yaml
arguments:
  telemetryQuery: "sum(rate(podparty_http_requests_count{...}[1m]))"
  topologyQuery: "(label = 'stackpack:kubernetes' and type = 'service')"
```

#### Dynamic Threshold Monitor Function

```yaml
arguments:
  telemetryQuery:
    query: "promql_query"
    unit: reqps
    aliasTemplate: "HTTP rate"
  topologyQuery: "(label = 'stackpack:kubernetes' and type = 'service')"
  falsePositiveRate: !!float 1e-8
  checkWindowMinutes: 10
  historicWindowMinutes: 120
  historySizeWeeks: 2
  includePreviousDay: false
  removeTrend: true
```

---

## Monitor Function Types

StackState provides several built-in monitor functions, and stackpacks can define custom ones.

### Built-in Common Monitor Functions

These are provided by the `common` stackpack dependency and referenced via URN:

| Monitor Function URN | Description | Use Case |
|---------------------|-------------|----------|
| `urn:stackpack:common:monitor-function:threshold` | Basic threshold comparison | Simple metric thresholds (CPU > 80%, errors > 5) |
| `urn:stackpack:common:monitor-function:topological-threshold` | Threshold with topology context | Trace-based metrics, service-level aggregations |
| `urn:stackpack:common:monitor-function:topology-health-aggregator-monitor-v2` | Aggregates child component health | Cluster/namespace health rollup |
| `urn:stackpack:common:monitor-function:derived-state-monitor` | Derives health from child states | Workload health from pod health |
| `urn:stackpack:common:monitor-function:topology-timestamp-threshold-monitor` | Time-based threshold | Certificate expiration |
| `urn:stackpack:common:monitor-function:topology-orphan-monitor` | Detects orphaned resources | Orphaned PVCs |
| `urn:stackpack:common:monitor-function:dynamic-threshold` | ML-based anomaly detection | Traffic anomalies, response time changes |

### Custom Monitor Functions

Stackpacks can define custom monitor functions with specialized logic. These require:

1. **Monitor Function Definition** (`monitor-function.sty`):
```yaml
- _type: MonitorFunction
  name: "Function name"
  identifier: "urn:stackpack:<name>:shared:monitor-function:<name>"
  id: -12345  # Numeric ID referenced by monitors
  parameters:
    - _type: Parameter
      name: parameterName
      type: STRING  # STRING, DOUBLE, LONG, BOOLEAN
      required: true|false
      multiple: true|false
  description: "Description"
  script:
    _type: ScriptFunctionBody
    scriptBody: |
      {{ include "./Monitor.groovy" }}
      {{ include "./Logging.groovy" }}
      {{ include "./Conversion.groovy" }}
```

2. **Groovy Implementation** (`Monitor.groovy`):
```groovy
// Shared utilities
{{ include "../Logging.groovy" }}
{{ include "../Conversion.groovy" }}
{{ include "../Topology.groovy" }}
{{ include "../Telemetry.groovy" }}
{{ include "../Validations.groovy" }}

// Health state constants
HEALTH_UNKNOWN_CONST = "UNKNOWN"
HEALTH_CLEAR_CONST = "CLEAR"
HEALTH_DEVIATING_CONST = "DEVIATING"
HEALTH_CRITICAL_CONST = "CRITICAL"

// Main evaluation function
return evaluate(arguments)
```

### Common Monitor Function IDs

Some built-in functions are referenced by numeric IDs:

| ID | Function |
|----|----------|
| `-1001` | Log monitoring |
| `-123` | AAD Anomaly Detection |
| `-1301` | Dynamic Threshold |

---

## Component Attachment via URN Templates

### How URN Templates Work

The `urnTemplate` field in a monitor's arguments specifies which components the monitor should attach to. The template uses variable placeholders `${variableName}` that are replaced at runtime with values from:

1. **PromQL metric labels** - from the query results
2. **Topology properties** - from component synchronization data
3. **Trace attributes** - from OpenTelemetry spans

### Common URN Patterns

#### Kubernetes Components

| Component Type | URN Template |
|----------------|--------------|
| Pod | `urn:kubernetes:/${cluster_name}:${namespace}:pod/${pod_name}` |
| Node | `urn:kubernetes:/${cluster_name}:node/${node}` |
| Service | `urn:kubernetes:/${cluster_name}:${namespace}:service/${service}` |
| Deployment | `urn:kubernetes:/${cluster_name}:${namespace}:deployment/${deployment}` |
| StatefulSet | `urn:kubernetes:/${cluster_name}:${namespace}:statefulset/${statefulset}` |
| Namespace | `urn:kubernetes:/${cluster_name}:namespace/${namespace}` |
| PVC | `urn:kubernetes:/${cluster_name}:${namespace}:persistent-volume-claim/${pvc_name}` |
| Cluster | `urn:cluster:/kubernetes:${cluster-name}` |

#### OpenTelemetry Components

| Component Type | URN Template |
|----------------|--------------|
| Service | `urn:opentelemetry:namespace/${service_namespace}:service/${service_name}` |
| Service Instance | `urn:opentelemetry:namespace/${service_namespace}:service/${service_name}:instance/${service_instance_name}` |
| Database | `urn:opentelemetry:namespace/${service_namespace}:service/${service_name}:db-system/${db_system}` |

#### Custom Components

| Component Type | URN Template |
|----------------|--------------|
| Generic | `urn:<source>:type/${type}:attribute/${value}` |

### Example: URN Template Variable Extraction

Given a PromQL query:
```promql
rate(container_cpu_usage_seconds_total{namespace="production", pod="api-server"}[5m])
```

The metric labels `namespace` and `pod` can be used in the URN template:
```yaml
urnTemplate: "urn:kubernetes:/${cluster_name}:${namespace}:pod/${pod}"
```

---

## Metric Queries and PromQL

### Writing Effective PromQL Queries for Monitors

Monitors use Prometheus Query Language (PromQL) to extract and transform telemetry data.

### Common Query Patterns

#### Rate Calculations
```promql
# Rate of increase over 5 minutes
rate(metric_name[5m])

# Sum rate by labels
sum by (pod_name) (rate(metric_name[5m]))
```

#### Histogram Quantiles
```promql
# 95th percentile latency
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# 99th percentile with multiple dimensions
histogram_quantile(0.99, sum by (service_name, le) (rate(span_duration_milliseconds_bucket[5m])))
```

#### Time Window Aggregations
```promql
# Average over 10 minutes
avg_over_time(metric_name[10m])

# Maximum over 5 minutes
max_over_time(metric_name[5m])

# Minimum over the last hour
min_over_time(metric_name[1h])
```

#### Delta Calculations
```promql
# Change over 1 minute
delta(metric_name[1m])
```

#### Prediction (for disk space)
```promql
# Predict disk full in 12 hours
predict_linear(disk_free_bytes[12h], 12 * 3600)
```

#### Fallback Values
```promql
# Return 0 if no data (prevents UNKNOWN state)
sum(increase(backup_successful[12h])) or 0
```

### Metric Units

| Unit | Description | Display |
|------|-------------|---------|
| `short` | Plain number | 1234 |
| `ms` | Milliseconds | 1234 ms |
| `percent` | Percentage (0-100) | 85% |
| `percentunit` | Percentage (0-1) | 0.85 |
| `cps` | Count per second | 100 cps |
| `bytes` | Bytes | 1.5 GB |
| `reqps` | Requests per second | 50 reqps |

### Label Filtering

Filter metrics using label selectors:
```promql
# Exact match
metric{label="value"}

# Regex match
metric{label=~"prefix.*"}

# Not equal
metric{label!="excluded"}
```

---

## Creating a New Monitor - Step by Step

### Step 1: Determine the Target Component Type

Identify what type of component you want to monitor:
- Is it a Kubernetes pod, service, deployment?
- Is it an OpenTelemetry service?
- Is it a custom component type?

### Step 2: Identify or Create the Metric

Determine what metric provides the data you need:
- Is there an existing metric from the stackpack?
- Do you need to create a new metric binding?
- What PromQL query extracts the right value?

### Step 3: Create the Monitor Directory

Create a new directory under your stackpack's provisioning templates:

```bash
mkdir -p src/main/stackpack/provisioning/templates/monitors/<monitor-name>/
```

### Step 4: Write the Monitor Definition

Create the `monitor.sty` file:

```yaml
- _type: Monitor
  name: "My Custom Monitor"
  identifier: "urn:stackpack:my-stackpack:shared:monitor:my-custom-monitor"
  description: |
    Monitors custom metric and alerts when threshold is exceeded.
  status: ENABLED
  tags:
    - my-stackpack
    - custom
  function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
  intervalSeconds: 30
  arguments:
    comparator: GT
    failureState: DEVIATING
    threshold: 100.0
    metric:
      query: 'rate(my_custom_metric{label="${label}"}[5m])'
      aliasTemplate: "Custom metric rate"
      unit: cps
    titleTemplate: "Custom metric"
    urnTemplate: "urn:my-source:/${cluster}:${namespace}:type/${name}"
  remediationHint: "{{ include './templates/monitors/my-custom-monitor/remediation-hint.md.hbs' 'identity' }}"
```

### Step 5: Create Remediation Hint (Optional but Recommended)

Create `remediation-hint.md.hbs`:

```markdown
# Remediation Guide

The custom metric for {{componentName}} has exceeded the threshold of {{threshold}}.

## Diagnosis Steps

1. Check the metric source
2. Verify the data pipeline
3. Review recent changes

## Resolution

Take appropriate action based on the diagnosis.
```

### Step 6: Include the Monitor in the StackPack Template

Add the monitor to your main provisioning template (e.g., `my-stackpack.sty`):

```yaml
nodes:
{{ include "./metricbindings.sty" "yaml" }}
{{ include "./templates/monitors/my-custom-monitor/monitor.sty" "yaml" }}
```

### Step 7: Test the Monitor

Run the stackpack test suite:
```bash
sbt test
```

---

## Remediation Hints

Remediation hints provide actionable guidance when a monitor enters a failure state.

### Template Variables

Remediation hints can use several variables from the monitor evaluation:

| Variable | Description |
|----------|-------------|
| `{{componentName}}` | Name of the affected component |
| `{{componentUrnForUrl}}` | Component URN formatted for URL |
| `{{threshold}}` | The threshold value that was exceeded |
| `{{currentValue}}` | The actual measured value |
| `{{healthState}}` | The resulting health state |

### Example Remediation Hint

```markdown
# High CPU Usage Detected

The CPU usage for component **{{componentName}}** has exceeded the threshold of {{threshold}}%.

Current value: **{{currentValue}}%**

## Recommended Actions

1. **Check Pod Status**
   - Review pod logs: `kubectl logs {{componentUrnForUrl}}`
   
2. **Analyze Resource Usage**
   - Check resource limits and requests
   - Look for resource-intensive operations

3. **Scale if Needed**
   - Consider scaling the deployment
   - Review auto-scaling configuration
```

---

## Best Practices

### 1. Naming Conventions

Follow consistent naming for monitor identifiers:
```
urn:stackpack:<stackpack-name>:shared:monitor:<descriptive-name>
```

Examples:
- `urn:stackpack:kubernetes-v2:shared:monitor:pod-cpu-throttling`
- `urn:stackpack:open-telemetry:shared:monitor:otel-service-span-duration`

### 2. Interval Selection

Choose appropriate intervals based on the metric:

| Metric Type | Recommended Interval |
|-------------|---------------------|
| High-frequency (CPU, memory) | 30 seconds |
| Medium-frequency (requests, errors) | 30-60 seconds |
| Low-frequency (backups, daily) | 300+ seconds |

### 3. Threshold Selection

- Start with conservative thresholds
- Adjust based on production data
- Consider both CRITICAL and DEVIATING states for graduated response

### 4. Health State Selection

| State | Use Case |
|-------|----------|
| `CRITICAL` | Immediate action required (service down, errors) |
| `DEVIATING` | Warning state, investigate soon |
| `CLEAR` | Normal operation |

### 5. Tagging

Add meaningful tags for filtering and organization:
```yaml
tags:
  - kubernetes
  - pod
  - cpu
  - resource
```

### 6. Always Include Remediation Hints

Help operators understand and resolve issues:
- Clear explanation of the problem
- Step-by-step diagnosis instructions
- Actionable resolution steps

---

## Advanced Patterns

### 1. Aggregated Health States

Roll up health from child to parent components:

```yaml
- _type: Monitor
  arguments:
    aggregatedHealthStateMetric: ...
    aggregationFunction: "worst"
    excludeSelfHealthState: true
  function: {{ get "urn:stackpack:common:monitor-function:topology-health-aggregator-monitor-v2" }}
```

### 2. Derived Health States

Derive health based on related component states:

```yaml
- _type: Monitor
  arguments:
    componentPattern: "type = 'deployment'"
    relationDirection: "children"
    healthStateMapping:
      CRITICAL: CRITICAL
      DEVIATING: DEVIATING
      CLEAR: CLEAR
  function: {{ get "urn:stackpack:common:monitor-function:derived-state-monitor" }}
```

### 3. Anomaly Detection

Use ML-based detection for unknown patterns:

```yaml
- _type: Monitor
  arguments:
    telemetryQuery: "rate(http_requests[1m])"
    topologyQuery: "type = 'service'"
  function: -123  # AAD Monitor Function ID
```

### 4. Dynamic Thresholds

Compare against historical baselines:

```yaml
- _type: Monitor
  arguments:
    telemetryQuery:
      query: "rate(requests[1m])"
      unit: reqps
    topologyQuery: "type = 'service'"
    historicWindowMinutes: 120
    checkWindowMinutes: 10
    falsePositiveRate: 1e-8
  function: -1301  # Dynamic Threshold
```

### 5. Disk Space Prediction

Predict when resources will be exhausted:

```yaml
metric:
  query: |
    100 - ((disk_available / disk_total) * 100) and
    100 - ((predict_linear(disk_available[12h], 12 * 3600) / disk_total) * 100) <= 99
```

### 6. Orphan Detection

Find resources not connected to the topology:

```yaml
- _type: Monitor
  arguments:
    query: "type = 'pvc'"
    relationFilter: "type = 'pod'"
    healthStateForOrphan: DEVIATING
  function: {{ get "urn:stackpack:common:monitor-function:topology-orphan-monitor" }}
```

---

## Monitor Provisioning

### How Monitors Are Loaded

Monitors are provisioned when the stackpack is installed or upgraded:

1. **Provisioning Script** (`*Provision.groovy`) imports the template
2. Template includes all monitor definitions
3. StackState creates monitor configurations
4. Monitors attach to matching components via URN templates

### Example Provisioning Script

```groovy
class MyStackPackProvision extends ProvisioningScript {
    @Override
    ProvisioningIO<scala.Unit> install(Map<String, Object> config) {
        return context().stackPack().importSnapshot("my-stackpack.sty", [:])
    }
}
```

---

## Testing Monitors

### Unit Testing

StackPacks include test suites that verify monitor behavior:

```bash
# Run all tests
sbt test

# Run specific test
sbt "testOnly *MonitorTest"
```

### Manual Testing

1. Install the stackpack in a test environment
2. Create components that match URN templates
3. Inject test metrics
4. Verify monitor states and remediation hints

### Debugging Tips

1. **Check metric labels**: Ensure PromQL query returns expected labels
2. **Verify URN matching**: Components must have matching URNs
3. **Review threshold units**: Ensure metric unit matches threshold scale
4. **Test remediation hints**: Verify template variables render correctly

---

## Quick Reference

### Monitor Function URNs

```
urn:stackpack:common:monitor-function:threshold
urn:stackpack:common:monitor-function:topological-threshold
urn:stackpack:common:monitor-function:topology-health-aggregator-monitor-v2
urn:stackpack:common:monitor-function:derived-state-monitor
urn:stackpack:common:monitor-function:topology-timestamp-threshold-monitor
urn:stackpack:common:monitor-function:topology-orphan-monitor
urn:stackpack:common:monitor-function:dynamic-threshold
```

### Comparator Values

- `GT` - Greater than
- `GTE` - Greater than or equal
- `LT` - Less than
- `LTE` - Less than or equal

### Health States

- `CLEAR` - Normal operation
- `DEVIATING` - Warning, needs attention
- `CRITICAL` - Immediate action required
- `UNKNOWN` - No data available

### Common Units

- `short` - Plain number
- `ms` - Milliseconds
- `percent` - Percentage (0-100)
- `percentunit` - Percentage (0-1)
- `cps` - Count per second
- `bytes` - Bytes
- `reqps` - Requests per second

---

## Additional Resources

- OpenTelemetry Monitor Creation Guide: `open-telemetry/monitor-creation-guide.md`
- Kubernetes-V2 Monitor Examples: `kubernetes-v2/src/main/stackpack/provisioning/monitors/`
- AAD-V2 Anomaly Detection: `aad-v2/src/main/stackpack/provisioning/anomaly-detection/`
- Prime Kubernetes Custom Functions: `prime-kubernetes/src/main/stackpack/provisioning/monitor_functions/`

---

*This guide was created by synthesizing monitor implementations across multiple StackPacks including OpenTelemetry, Kubernetes-V2, AAD-V2, Notification-Operator, StackState, and Prime Kubernetes.*
