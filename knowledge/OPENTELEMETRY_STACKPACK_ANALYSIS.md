# OpenTelemetry StackPack - Comprehensive Technical Analysis

## Executive Summary

The OpenTelemetry StackPack is a sophisticated integration that transforms distributed tracing data and metrics from OpenTelemetry-instrumented applications into a dynamic, queryable topology graph. Unlike traditional StackPacks that consume from configuration-specific Kafka topics, the OpenTelemetry StackPack uses a **fixed internal topic** (`sts_topo_opentelemetry_collector`) and derives topology automatically from trace spans and resource attributes.

**Key Distinguishing Features:**
- **Trace-driven topology**: Components and relations are inferred from distributed trace spans
- **No agent configuration**: Data flows directly via OTLP (OpenTelemetry Protocol)
- **Real-time dynamic discovery**: Services, instances, and dependencies emerge automatically
- **Multi-language support**: Out-of-the-box metrics for Java, .NET, and generic span metrics
- **Service graph construction**: Relations derived from span parent-child relationships

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Ingestion Pipeline](#data-ingestion-pipeline)
3. [Component Discovery and Creation](#component-discovery-and-creation)
4. [Component Types](#component-types)
5. [Relation Types](#relation-types)
6. [Metric Bindings](#metric-bindings)
7. [Monitors](#monitors)
8. [Data Processing Functions](#data-processing-functions)
9. [Configuration](#configuration)
10. [Comparison with Other StackPacks](#comparison-with-other-stackpacks)

---

## Architecture Overview

### High-Level Flow

```
┌──────────────────┐
│ Instrumented App │ (OTel SDK)
└────────┬─────────┘
         │ OTLP/gRPC or HTTP
         ▼
┌─────────────────────────┐
│ SUSE Observability      │
│ OTLP Receiver           │
└────────┬────────────────┘
         │ Processes & enriches
         ▼
┌──────────────────────────────────┐
│ Internal Kafka Topic:            │
│ sts_topo_opentelemetry_collector │
└────────┬─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Topology Sync Process   │
│ (reads from topic)      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Component Mapping       │
│ Function (Groovy)       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Component Template      │
│ Function (Handlebars)   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ StackState Topology DB  │
│ (Components & Relations)│
└─────────────────────────┘
```

### Key Differences from Traditional StackPacks

| Aspect | Traditional StackPacks | OpenTelemetry StackPack |
|--------|----------------------|------------------------|
| **Data Source** | Agent checks (Zabbix, K8s, etc.) | OTLP Receiver (traces + metrics) |
| **Topic Name** | Dynamic per instance | Fixed: `sts_topo_opentelemetry_collector` |
| **Topology Origin** | Explicit API data | Inferred from trace spans |
| **Configuration** | Instance-specific | Global, no instances |
| **Component Discovery** | Static/polling | Dynamic/trace-driven |
| **Relations** | Explicit relationships | Derived from span parent-child |

---

## Data Ingestion Pipeline

### Step 1: OTLP Reception

Applications instrumented with OpenTelemetry SDKs send telemetry data to SUSE Observability's OTLP receiver:

**Supported Formats:**
- **gRPC**: `otlp/v1/traces` and `otlp/v1/metrics`
- **HTTP/JSON**: `v1/traces` and `v1/metrics`

**Required Authentication:**
- Service token (API key) for SUSE Observability

**Example Configuration (OTel Collector):**
```yaml
exporters:
  otlp:
    endpoint: https://your-instance.stackstate.io:443
    headers:
      "StackState-Api-Key": "your-service-token"
```

### Step 2: Internal Processing

The OTLP receiver:
1. **Validates** incoming traces and metrics
2. **Enriches** data with resource attributes (service.name, k8s.pod.name, etc.)
3. **Converts** trace data into topology elements
4. **Publishes** to the internal Kafka topic

**Topic Configuration:**
```yaml
_type: Sts.StsTopologyDataSourceConfig
topic: sts_topo_opentelemetry_collector
integrationType: opentelemetry
supportedDataTypes:
  - TOPOLOGY_ELEMENTS
autoExpireElements: true
expireElementsAfter: 900000  # 15 minutes
```

**Auto-Expiration:** Components that don't receive updates for 15 minutes are automatically removed. This ensures the topology reflects only active services.

### Step 3: Topology Synchronization

A continuous background process reads from the Kafka topic:

**Sync Configuration:**
```yaml
_type: Sync
topologyDataQuery:
  _type: Sts.StsTopologyElementsQuery
  consumerOffsetStartAtEarliest: false
  componentIdExtractorFunction: default-function
  relationIdExtractorFunction: default-function
```

**Processing Characteristics:**
- **Batch Size**: 200 elements per batch
- **Rate Limit**: 5 batches per second
- **Offset Strategy**: Start from latest (not earliest)

### Step 4: Mapping and Templating

Each topology element passes through two transformation stages:

#### Component Mapping Function (Groovy)
**Purpose**: Normalize and enrich topology elements

**Location:** `templates/sync/component-mapping-function.groovy`

**Key Operations:**
1. Initialize empty `tags` and `properties` maps
2. Extract `service.namespace` and create namespace identifier
3. Normalize component type names (`service_instance` → `service-instance`)
4. Create hierarchical identifiers for linking
5. Add `stackpack:open-telemetry` label

#### Component Template Function (Handlebars)
**Purpose**: Convert mapped elements into StackState components

**Location:** `templates/sync/component-template.json.handlebars`

**Output Structure:**
```json
{
  "_type": "Component",
  "name": "...",
  "type": "...",
  "labels": [...],
  "layer": "services",
  "domain": "opentelemetry",
  "environments": ["production"],
  "properties": {...}
}
```

---

## Component Discovery and Creation

### How Components Are Discovered

The OpenTelemetry StackPack discovers components from **resource attributes** attached to spans:

#### Standard OTel Resource Attributes

| Attribute | Purpose | Component Type |
|-----------|---------|---------------|
| `service.name` | Logical service identifier | `otel service` |
| `service.namespace` | Service grouping | `service namespace (otel)` |
| `service.instance.id` | Unique instance identifier | `otel service instance` |
| `db.system` + `db.name` | Database identification | `database` |
| `k8s.pod.name` | Kubernetes pod | `pod` |
| `k8s.cluster.name` | K8s cluster metadata | (metadata only) |
| `host.name` | Host/VM identification | (potential future component) |

### Component Creation Logic

#### Service Components

**URN Pattern:** `urn:opentelemetry:namespace/{namespace}:service/{service.name}`

**Created When:**
- A span with `service.name` and `service.namespace` is received
- Automatically aggregates all instances of the same service

**Tags Extracted:**
```yaml
service.name: "checkout-service"
service.namespace: "production"
telemetry.sdk.language: "java"
telemetry.sdk.version: "1.32.0"
```

**Properties Added:**
```yaml
namespaceIdentifier: "urn:opentelemetry:namespace/production"
```

#### Service Instance Components

**URN Pattern:** `urn:opentelemetry:namespace/{namespace}:service/{service.name}:serviceInstance/{instance.id}`

**Created When:**
- A span includes `service.instance.id` (typically hostname or pod name)

**Component Mapping Logic:**
```groovy
case "service_instance":
case "service-instance":
    element.type.name = "service-instance"
    def namespace = element.data.tags["service.namespace"]
    def serviceName = element.data.tags["service.name"]

    element.data.properties.put(
        "serviceIdentifier",
        "urn:opentelemetry:namespace/${namespace}:service/${serviceName}".toString()
    )
    break
```

**Hierarchy:**
- Service Instance → (provided-by) → Service
- Service Instance → (kubernetes-to-otel) → Pod (if K8s metadata present)

#### Database Components

**URN Pattern:** `urn:opentelemetry:database:{db.system}:{db.name}` (inferred)

**Created When:**
- Spans with `span.kind = SPAN_KIND_CLIENT` and `db.system` attribute
- Common systems: `postgresql`, `mysql`, `mongodb`, `redis`

**Tags Extracted:**
```yaml
db.system: "postgresql"
db.name: "orders_db"
db.connection_string: "postgresql://db-host:5432"
```

#### Service Namespace Components

**URN Pattern:** `urn:opentelemetry:namespace/{namespace}`

**Created When:**
- Any service with a `service.namespace` attribute is discovered

**Component Mapping Logic:**
```groovy
case "namespace":
case "service-namespace":
    element.type.name = "service-namespace"
    break
```

**Purpose:** Organizational grouping of services (e.g., `production`, `staging`, `team-alpha`)

---

## Component Types

### 1. otel service

**Identifier:** `urn:stackpack:open-telemetry:shared:component-type:service`

**Description:** Logical service representing all instances of a deployed application

**Key Fields:**
- **Type**: Service type (auto-extracted)
- **Health**: Aggregated health from monitors
- **Namespace**: Link to service namespace
- **Labels**: All resource attributes as labels

**Metrics Categories:**
1. **Traces**
   - Span rate (calls per second)
   - Span error rate (percentage)
   - Span duration (95th percentile)

2. **Service**
   - Service instance count

**Related Resources:**
- **Instances**: All service instances belonging to this service
- **Related Services**: Services connected via trace spans

**Trace Binding:**
```yaml
filter:
  attributes:
    service.namespace: ["${tags.service.namespace}"]
    service.name: ["${name}"]
```

Shows all traces for this service regardless of instance.

### 2. otel service instance

**Identifier:** `urn:stackpack:open-telemetry:shared:component-type:service-instance`

**Description:** A specific running instance of a service (container, VM, process)

**Key Fields:**
- **Type**: Instance type
- **Health**: Instance-specific health
- **Namespace**: Link to service namespace
- **Service**: Link to parent service
- **Labels**: Instance-specific attributes

**Metrics Categories:**
1. **Traces** (same as service, but instance-scoped)

**Language-Specific Metrics (if available):**

**Java (JVM):**
- GC durations (95th percentile)
- GC per second
- Heap memory
- Non-heap memory
- Memory after last GC

**.NET:**
- GC heap sizes
- GC counts
- Exception counts

**Trace Binding:**
```yaml
filter:
  attributes:
    service.instance.id: ["${tags.service.instance.id}"]
    service.namespace: ["${tags.service.namespace}"]
    service.name: ["${tags.service.name}"]
```

Shows traces specific to this instance.

### 3. database

**Identifier:** `urn:stackpack:open-telemetry:shared:component-type:database`

**Description:** External database or data store accessed by services

**Key Fields:**
- **Type**: Database type (PostgreSQL, MySQL, MongoDB, etc.)
- **Health**: Based on span error rates
- **Labels**: Database connection metadata

**Metrics:**
- Database span rate
- Database span error rate
- Database span duration

**How Discovered:**
- From `CLIENT` spans with `db.system` attribute
- Extracted from trace context when service makes database calls

### 4. service namespace (otel)

**Identifier:** `urn:stackpack:open-telemetry:shared:component-type:service-namespace`

**Description:** Logical grouping for services (environment, team, application)

**Key Fields:**
- **Type**: Namespace
- **Health**: Aggregated from contained services
- **Labels**: Namespace metadata

**Related Resources:**
- **Services**: All services in this namespace
- **Service Instances**: All instances in this namespace

**Common Namespace Values:**
- `production`, `staging`, `development`
- Team names: `team-checkout`, `platform`
- Application groups: `ecommerce`, `analytics`

### 5. pod

**Identifier:** `urn:stackpack:open-telemetry:shared:component-type:pod`

**Description:** Kubernetes pod hosting service instances

**Purpose:** Links OpenTelemetry services to Kubernetes infrastructure

**Discovered From:**
- `k8s.pod.name`
- `k8s.namespace.name`
- `k8s.cluster.name`

**Note:** Minimal definition in the StackPack; enriched when Kubernetes StackPack is also installed.

---

## Relation Types

Relations in the OpenTelemetry StackPack represent dependencies and hierarchies inferred from trace data.

### 1. provided-by (Hierarchical)

**Identifier:** `urn:stackpack:open-telemetry:shared:relation-type:provided-by`

**Direction:** ONE_WAY
**Type:** HIERARCHICAL

**Usage:**
- Service Instance → Service
- Service → Service Namespace

**Example:**
```
checkout-service-pod-abc123 (instance)
    ↓ provided-by
checkout-service
    ↓ provided-by
production (namespace)
```

### 2. synchronous (Connection)

**Identifier:** `urn:stackpack:open-telemetry:shared:relation-type:synchronous`

**Direction:** ONE_WAY
**Type:** CONNECTION

**Usage:**
- Service → Service (HTTP, gRPC calls)
- Derived from `SPAN_KIND_CLIENT` → `SPAN_KIND_SERVER` span relationships

**Discovery Logic:**
- Parent span from Service A
- Child span from Service B
- If same trace ID and parent-child relationship exists → synchronous connection

**Example:**
```
api-gateway → (synchronous) → checkout-service
```

### 3. asynchronous (Connection)

**Identifier:** `urn:stackpack:open-telemetry:shared:relation-type:asynchronous`

**Direction:** ONE_WAY
**Type:** CONNECTION

**Usage:**
- Service → Service (message queue, event streaming)
- Derived from `SPAN_KIND_PRODUCER` → `SPAN_KIND_CONSUMER` span relationships

**Example:**
```
order-service → (asynchronous) → notification-service
  (via Kafka topic: order-events)
```

### 4. database (Connection)

**Identifier:** `urn:stackpack:open-telemetry:shared:relation-type:database`

**Direction:** ONE_WAY
**Type:** CONNECTION

**Usage:**
- Service Instance → Database
- Derived from `SPAN_KIND_CLIENT` spans with `db.system` attribute

**Example:**
```
checkout-service-instance-1 → (database) → orders_db (PostgreSQL)
```

### 5. kubernetes-to-otel (Unclassified)

**Identifier:** `urn:stackpack:open-telemetry:shared:relation-type:kubernetes-to-otel`

**Direction:** NONE
**Type:** UNCLASSIFIED

**Usage:**
- Pod → Service Instance
- Created when `k8s.pod.name` matches service instance

**Purpose:** Cross-StackPack integration with Kubernetes StackPack

---

## Metric Bindings

Metric bindings link Prometheus-format metrics to components, enabling visualizations and monitoring.

### Span Metrics (All Component Types)

These metrics are derived from trace spans and aggregated by the SUSE Observability backend:

#### 1. Span Rate (otel_span_calls_total)

**Metric:** `otel_span_calls_total`
**Type:** Counter
**Unit:** Calls per second (cps)

**Query (Service Instance):**
```promql
sum(rate(otel_span_calls_total{
  service_namespace="${tags.service.namespace}",
  service_name="${tags.service.name}",
  service_instance_id="${tags.service.instance.id}"
}[${__rate_interval}])) by (span_kind)
```

**Query (Service):**
```promql
sum(rate(otel_span_calls_total{
  service_namespace="${tags.service.namespace}",
  service_name="${name}"
}[${__rate_interval}])) by (span_kind)
```

**Chart:** Line chart showing:
- All spans (by kind: SERVER, CLIENT, PRODUCER, CONSUMER)
- Error spans

#### 2. Span Error Rate

**Type:** Derived
**Unit:** Percent (0-1)

**Formula:**
```promql
(sum(rate(otel_span_calls_total{
  status_code="STATUS_CODE_ERROR",
  service_namespace="${tags.service.namespace}",
  service_name="${name}"
}[5m])) by (span_kind) or 0)
/
sum(rate(otel_span_calls_total{
  service_namespace="${tags.service.namespace}",
  service_name="${name}"
}[5m])) by (span_kind)
```

**Interpretation:**
- 0.0 = 0% errors
- 0.05 = 5% error rate
- 1.0 = 100% errors

#### 3. Span Duration (95th percentile)

**Metric:** `otel_span_duration_milliseconds_bucket`
**Type:** Histogram
**Unit:** Milliseconds

**Query:**
```promql
histogram_quantile(0.95, sum(rate(
  otel_span_duration_milliseconds_bucket{
    service_namespace="${tags.service.namespace}",
    service_name="${tags.service.name}",
    service_instance_id="${tags.service.instance.id}"
  }[${__rate_interval}]
)) by (k8s_cluster_name, k8s_namespace_name, k8s_pod_name, span_kind, le))
```

**Interpretation:**
- 95% of spans complete faster than this value
- Useful for SLA monitoring (e.g., "95% of requests < 500ms")

### JVM Metrics (Java Service Instances)

Available when `telemetry.sdk.language = "java"`

#### 1. GC Durations (95th Percentile)

**Metric:** `jvm_gc_duration_seconds_bucket`

**Query:**
```promql
histogram_quantile(0.95, rate(
  jvm_gc_duration_seconds_bucket{
    service_namespace="${tags.service.namespace}",
    service_name="${tags.service.name}",
    service_instance_id="${name}"
  }[${__rate_interval}]
))
```

**Unit:** Seconds
**Grouped By:** `jvm_gc_name` (e.g., `G1 Young Generation`, `G1 Old Generation`)

#### 2. GC Per Second

**Metric:** `jvm_gc_duration_seconds_count`

**Query:**
```promql
rate(jvm_gc_duration_seconds_count{
  service_namespace="${tags.service.namespace}",
  service_name="${tags.service.name}",
  service_instance_id="${name}"
}[${__rate_interval}])
```

**Unit:** Collections per second

#### 3. Heap Memory

**Metric:** `jvm_memory_used_bytes`

**Query:**
```promql
jvm_memory_used_bytes{
  service_namespace="${tags.service.namespace}",
  service_name="${tags.service.name}",
  service_instance_id="${name}",
  jvm_memory_type="heap"
}
```

**Unit:** Bytes
**Grouped By:** `jvm_memory_pool_name` (e.g., `G1 Eden Space`, `G1 Old Gen`)

#### 4. Memory After Last GC

**Metric:** `jvm_memory_used_after_last_gc_bytes`

**Query:**
```promql
jvm_memory_used_after_last_gc_bytes{
  service_namespace="${tags.service.namespace}",
  service_name="${tags.service.name}",
  service_instance_id="${name}"
}
```

**Purpose:** Shows memory usage after GC, useful for detecting memory leaks

### .NET Metrics

Available when `telemetry.sdk.language = "dotnet"`

**Metrics Include:**
- GC heap sizes (Gen 0, Gen 1, Gen 2, LOH)
- GC counts per generation
- Exception counts
- Thread pool metrics

### Layout Specification

Metrics appear in different UI locations:

#### Metric Perspective
```yaml
layout:
  metricPerspective:
    tab: "Traces Performance"  # or "JVM", ".NET"
    section: "Spans"            # or "GC", "Memory"
    weight: 1                    # ordering within section
```

#### Component Summary
```yaml
layout:
  componentSummary:
    weight: 1  # shown in component overview page
```

#### Component Highlight
```yaml
layout:
  componentHighlight:
    section: "GC"  # highlighted in component details
```

---

## Monitors

Monitors continuously evaluate metrics and update component health states.

### Monitor Architecture

**Function Used:** `urn:stackpack:common:monitor-function:threshold`

**Evaluation:**
- Runs every 30 seconds (`intervalSeconds: 30`)
- Executes PromQL query
- Compares result against threshold
- Updates component health if threshold breached

**URN Template:**
Matches monitor results to components using resource attributes:
```yaml
urnTemplate: "urn:opentelemetry:namespace/${service_namespace}:service/${service_name}"
```

### 1. Service Span Duration Monitor

**Identifier:** `urn:stackpack:open-telemetry:shared:monitor:otel-service-span-duration`

**Purpose:** Detect slow services

**Query:**
```promql
histogram_quantile(0.95, sum by(service_namespace, service_name, le)(
  rate(otel_span_duration_milliseconds_bucket{
    span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"
  }[5m])
))
```

**Threshold:** 5000ms (default)
**Failure State:** DEVIATING (yellow)

**Interpretation:**
- If 95th percentile span duration > 5000ms, service is marked as deviating
- Only monitors server-side and consumer spans (not client calls)

**Remediation Hint:**
```markdown
The 95th percentile of the span duration for this service is high.
This could indicate:
- Performance degradation
- Increased load
- Downstream dependency issues
- Resource contention

Recommended actions:
1. Check service instance metrics for resource usage
2. Review related service dependencies
3. Examine trace details for slow operations
```

### 2. Service Span Error Ratio Monitor

**Identifier:** `urn:stackpack:open-telemetry:shared:monitor:otel-service-span-error-ratio`

**Purpose:** Detect services with high error rates

**Query:**
```promql
(sum by(service_namespace, service_name)(
  rate(otel_span_calls_total{
    status_code="STATUS_CODE_ERROR",
    span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"
  }[5m])
) or 0)
/
sum by(service_namespace, service_name)(
  rate(otel_span_calls_total{
    span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"
  }[5m])
)
```

**Threshold:** 0.05 (5% error rate, default)
**Failure State:** DEVIATING

**Interpretation:**
- If error rate exceeds 5%, service health degrades
- Only considers server-side errors (not client errors from calling other services)

### 3. Service Instance Span Duration Monitor

**Identifier:** `urn:stackpack:open-telemetry:shared:monitor:otel-service-instance-span-duration`

**Purpose:** Detect slow service instances

**Scope:** Instance-level (includes `service_instance_id` in query)

**Threshold:** 5000ms
**Failure State:** DEVIATING

**Use Case:**
- Identify specific problematic instances in a service
- Useful for detecting degraded containers/VMs in a deployment

### 4. Service Instance Span Error Ratio Monitor

**Identifier:** `urn:stackpack:open-telemetry:shared:monitor:otel-service-instance-span-error-ratio`

**Purpose:** Detect instances with high error rates

**Threshold:** 0.05 (5%)
**Failure State:** DEVIATING

### 5. Database Span Duration Monitor

**Identifier:** `urn:stackpack:open-telemetry:shared:monitor:otel-database-span-duration`

**Purpose:** Detect slow database operations

**Query:**
```promql
histogram_quantile(0.95, sum by(db_system, db_name, le)(
  rate(otel_span_duration_milliseconds_bucket{
    span_kind="SPAN_KIND_CLIENT",
    db_system!=""
  }[5m])
))
```

**Threshold:** 1000ms (default)
**Failure State:** DEVIATING

**Interpretation:**
- If database queries take > 1000ms at 95th percentile, database component degrades
- Helps identify database performance issues

---

## Data Processing Functions

### Component Mapping Function

**File:** `templates/sync/component-mapping-function.groovy`

**Purpose:** Normalize and enrich incoming topology elements before template rendering

**Full Code:**
```groovy
if (!element.data.containsKey("tags")) {
  element.data.put("tags", [:])
}

if (!element.data.containsKey("properties")) {
    element.data.put("properties", [:])
}

if (element.data.tags.containsKey("service.namespace")) {
    def namespace = element.data.tags["service.namespace"]
    element.data.properties.put("namespaceIdentifier", "urn:opentelemetry:namespace/${namespace}".toString())
}

switch (element.type.name) {
  case "namespace":
  case "service-namespace":
    element.type.name = "service-namespace"
    break;
  case "service_instance":
  case "service-instance":
    element.type.name = "service-instance"
    def namespace = element.data.tags["service.namespace"]
    def serviceName = element.data.tags["service.name"]

    element.data.properties.put("serviceIdentifier", "urn:opentelemetry:namespace/${namespace}:service/${serviceName}".toString())
    break;
}

element.data.tags.put("stackpack", "open-telemetry")

element
```

**Key Transformations:**

1. **Defensive Initialization:**
   - Ensures `tags` and `properties` maps exist
   - Prevents null pointer exceptions

2. **Namespace Identifier:**
   - Creates URN for service namespace
   - Used for component linking in UI

3. **Type Normalization:**
   - Standardizes `service_instance` → `service-instance`
   - Handles both `namespace` and `service-namespace` inputs

4. **Service Identifier:**
   - Creates hierarchical URN linking instance to service
   - Enables "Related Resources" queries

5. **StackPack Tagging:**
   - Adds `stackpack:open-telemetry` label
   - Used for filtering and scoping

**Input Example:**
```json
{
  "externalId": "urn:opentelemetry:namespace/prod:service/api:serviceInstance/pod-123",
  "type": {"name": "service_instance"},
  "data": {
    "name": "api-pod-123",
    "tags": {
      "service.name": "api",
      "service.namespace": "prod",
      "service.instance.id": "pod-123",
      "k8s.pod.name": "api-pod-123"
    }
  }
}
```

**Output Example:**
```json
{
  "externalId": "urn:opentelemetry:namespace/prod:service/api:serviceInstance/pod-123",
  "type": {"name": "service-instance"},
  "data": {
    "name": "api-pod-123",
    "tags": {
      "service.name": "api",
      "service.namespace": "prod",
      "service.instance.id": "pod-123",
      "k8s.pod.name": "api-pod-123",
      "stackpack": "open-telemetry"
    },
    "properties": {
      "namespaceIdentifier": "urn:opentelemetry:namespace/prod",
      "serviceIdentifier": "urn:opentelemetry:namespace/prod:service/api"
    }
  }
}
```

### Component Template Function

**File:** `templates/sync/component-template.json.handlebars`

**Purpose:** Transform mapped elements into StackState component JSON

**Full Template:**
```handlebars
{
  "_type": "Component",
  "labels": [
    \{{#if element.data.tags\}}
    \{{# join element.data.tags ","\}}
        {
        "_type": "Label",
        "name": "\{{key\}}:\{{this\}}"
        }
    \{{/ join \}}
    \{{/if\}}
    ],
  "name": "\{{#if element.data.name\}}\{{ element.data.name \}}\{{else\}}\{{ element.externalId \}}\{{/if\}}",
  "type" : \{{ getOrCreate (identifier "urn:stackpack:open-telemetry:shared" "ComponentType" element.type.name) (identifier "urn:system:auto" "ComponentType" element.type.name) (concat "Type=ComponentType;Name=" element.type.name) \}},
  "version": "\{{ element.data.version \}}",
  "layer" : \{{ get "urn:stackpack:common:layer:services" \}},
  "domain": \{{ get "urn:stackpack:open-telemetry:shared:domain:opentelemetry" \}},
  "environments": [
    \{{ get "urn:stackpack:common:environment:production" \}}
  ],
  "properties": {
    \{{#if element.data.properties\}}
        \{{# join element.data.properties ","\}}
            "\{{key\}}": "\{{this\}}"
        \{{/ join \}}
    \{{/if\}}
  }
}
```

**Key Features:**

1. **Label Conversion:**
   - All tags become labels (`key:value` format)
   - Used for filtering and querying

2. **Component Type Resolution:**
   - First tries: `urn:stackpack:open-telemetry:shared:component-type:{name}`
   - Fallback: `urn:system:auto:component-type:{name}`
   - Auto-creates types if not predefined

3. **Layer Assignment:**
   - All OTel components go to "Services" layer
   - Ensures consistent topology visualization

4. **Domain Assignment:**
   - All belong to "opentelemetry" domain
   - Separates from other integrations

5. **Environment:**
   - Defaults to "production"
   - Can be overridden via tags

**Handlebars Helpers:**

- `join`: Iterates over maps/arrays
- `get`: Retrieves existing StackState objects by URN
- `getOrCreate`: Creates object if not exists
- `identifier`: Constructs URN
- `concat`: String concatenation

### Relation Template Function

**File:** `templates/sync/relation-template.json.handlebars`

**Purpose:** Transform topology relations into StackState relations

**Full Template:**
```handlebars
{
  "_type": "Relation",
  "checks": [],
  "streams": [],
  "labels": [
    \{{#if element.data.tags\}}
    \{{# join element.data.tags ","\}}
        {
            "_type": "Label",
            "name": "\{{key\}}:\{{this\}}"
        }
    \{{/ join \}}
    \{{/if\}}
  ],
  "name": "\{{ element.sourceExternalId \}} --> \{{ element.targetExternalId \}}",
  "type": \{{getOrCreate (identifier "urn:stackpack:open-telemetry:shared" "RelationType" element.type.name ) (identifier "urn:system:auto" "RelationType" element.type.name) (concat "Type=RelationType;Name=" element.type.name) \}},
  "dependencyDirection": "ONE_WAY",
  "source": \{{ element.sourceId \}},
  "target": \{{ element.targetId \}}
}
```

**Key Features:**

1. **Relation Naming:**
   - Descriptive: `source --> target`
   - Helps in debugging topology

2. **Type Resolution:**
   - Similar to component types
   - Auto-creates unknown relation types

3. **Dependency Direction:**
   - Always `ONE_WAY` for OTel
   - Represents call direction (caller → callee)

4. **Label Preservation:**
   - Carries over all tags from source data
   - Useful for relation filtering

---

## Configuration

### StackPack Configuration File

**File:** `stackpack.conf`

```conf
name = "open-telemetry"
displayName = "Open Telemetry"
categories = [ "Open Telemetry" ]
releaseStatus = AVAILABLE
isNew = true
isMultiConfig = false
provision = "OpenTelemetryProvision"
dependencies {
  common: "3.4.2"
}
```

**Key Properties:**

- **isMultiConfig: false** - Only one instance allowed (global StackPack)
- **No config steps** - No user configuration required
- **Dependency:** Requires `common` StackPack v3.4.2+

### Provisioning Script

**File:** `OpenTelemetryProvision.groovy`

```groovy
class OpenTelemetryProvision extends ProvisioningScript {

  @Override
  ProvisioningIO<scala.Unit> install(Map<String, Object> config) {
    return context().stackPack().importSnapshot("templates/open-telemetry.sty", [:])
  }

  @Override
  ProvisioningIO<scala.Unit> upgrade(Map<String, Object> config, Version current) {
    return install(config)
  }
}
```

**Characteristics:**

1. **No `waitingForData`:** Unlike other StackPacks, doesn't wait for specific topic data
2. **Simple install:** Just imports templates, no dynamic configuration
3. **Idempotent upgrade:** Same logic as install

**Why No `waitingForData`?**
- Data flows continuously via OTLP receiver
- No specific "instance" to wait for
- Topology appears as soon as traces arrive

### Data Source Configuration

**From:** `templates/sync/synchronization.sty`

```yaml
_type: DataSource
name: "Open Telemetry"
identifier: "urn:stackpack:open-telemetry:shared:data-source:opentelemetry"
config:
  autoExpireElements: true
  expireElementsAfter: 900000  # 15 minutes
  integrationType: opentelemetry
  supportedDataTypes:
    - TOPOLOGY_ELEMENTS
  topic: sts_topo_opentelemetry_collector
```

**Critical Settings:**

- **autoExpireElements: true** - Components auto-delete if no updates
- **expireElementsAfter: 900000** - 15 minutes TTL
- **Fixed topic name** - Not dynamic like other StackPacks

**Expiration Logic:**
```
If no updates for component in 15 minutes:
  → Component marked as stale
  → Component removed from topology
  → Relations cleaned up
```

This ensures topology reflects only active services.

---

## Comparison with Other StackPacks

### OpenTelemetry vs Kubernetes StackPack

| Aspect | OpenTelemetry | Kubernetes |
|--------|--------------|------------|
| **Data Source** | OTLP traces/metrics | K8s API |
| **Topic** | `sts_topo_opentelemetry_collector` | `sts-topo-kubernetes-{cluster}` |
| **Component Types** | Services, instances, databases | Pods, deployments, services, nodes |
| **Relation Source** | Trace spans | K8s metadata |
| **Auto-Expire** | 15 minutes | 3 hours |
| **Configuration** | None | Cluster name required |
| **Integration** | Can link pods to service instances via `kubernetes-to-otel` relation |

**Combined Usage:**
When both are installed:
- K8s provides infrastructure layer (pods, nodes, namespaces)
- OTel provides application layer (services, instances)
- Cross-linked via pod names

### OpenTelemetry vs Dynatrace StackPack

| Aspect | OpenTelemetry | Dynatrace |
|--------|--------------|-----------|
| **Data Source** | OTel SDKs (open) | Dynatrace OneAgent (proprietary) |
| **Instrumentation** | Manual SDK integration | Automatic injection |
| **Topic** | Fixed internal | `sts-topo-dynatrace-{tenant}` |
| **Topology Depth** | Application services | Full-stack (hosts, processes, services) |
| **Metrics** | Prometheus-format | Dynatrace proprietary |
| **Cost** | Free (open source) | Dynatrace license required |

**When to Use:**
- **OpenTelemetry**: Open-source, cloud-native apps, multi-vendor
- **Dynatrace**: Enterprise monitoring, deep diagnostics, legacy apps

### OpenTelemetry vs StackState Agent V2

| Aspect | OpenTelemetry | Agent V2 |
|--------|--------------|----------|
| **Focus** | Application traces | Infrastructure & processes |
| **Topic** | `sts_topo_opentelemetry_collector` | `sts-topo-process-agents` |
| **Component Types** | Services, instances | Hosts, processes, containers |
| **Metrics Source** | Trace-derived + runtime | System metrics |
| **Instrumentation** | Application-level | System-level |

**Complementary:**
- Agent V2 provides host/process topology
- OTel provides service/application topology
- Together: Full-stack observability

---

## Advanced Topics

### Custom Component Types

The template function auto-creates component types:

```handlebars
\{{ getOrCreate
    (identifier "urn:stackpack:open-telemetry:shared" "ComponentType" element.type.name)
    (identifier "urn:system:auto" "ComponentType" element.type.name)
    (concat "Type=ComponentType;Name=" element.type.name)
\}}
```

**How It Works:**
1. Tries to find: `urn:stackpack:open-telemetry:shared:component-type:{name}`
2. If not found, creates: `urn:system:auto:component-type:{name}`
3. Auto-created types have minimal configuration

**Use Case:**
If your application creates components with `type.name = "cache"`, the system auto-creates a `cache` component type.

**Best Practice:**
For production, define explicit component types in templates:
```yaml
- _type: "ComponentType"
  identifier: "urn:stackpack:open-telemetry:shared:component-type:cache"
  name: "cache"
  iconbase64: "..."
  highlights: {...}
```

### Service Graph Metrics

Advanced metric: `traces_service_graph_request_total`

**Purpose:** Pre-computed service-to-service request rates

**Dimensions:**
- `client_service_namespace`
- `client_service_name`
- `server_service_namespace`
- `server_service_name`

**Usage:**
```promql
sum by (client_service_name, server_service_name)(
  rate(traces_service_graph_request_total[5m])
)
```

**Benefit:** Faster than computing from raw spans

### Trace Context Propagation

The StackPack relies on proper trace context propagation:

**Required Headers (HTTP):**
```
traceparent: 00-{trace-id}-{span-id}-01
tracestate: vendor=value
```

**gRPC Metadata:**
```
grpc-trace-bin: {binary trace context}
```

**Without Propagation:**
- Services appear disconnected
- Relations not created
- Distributed tracing breaks

### Multi-Cluster Scenarios

**Problem:** Multiple K8s clusters sending to same SUSE Observability instance

**Solution:** Use `k8s.cluster.name` attribute

**Component URN:**
```
urn:opentelemetry:cluster/{cluster}:namespace/{namespace}:service/{service}
```

**Benefit:** Services with same name in different clusters don't collide

---

## Troubleshooting

### No Components Appearing

**Possible Causes:**

1. **OTLP endpoint not configured:**
   - Verify OTel Collector/SDK exports to correct URL
   - Check service token authentication

2. **Missing resource attributes:**
   - Ensure `service.name` and `service.namespace` are set
   - Check OTel SDK resource configuration

3. **Receiver not processing:**
   - Check SUSE Observability receiver logs
   - Verify Kafka topic `sts_topo_opentelemetry_collector` has data

4. **Auto-expiration:**
   - Components expire after 15 minutes without updates
   - Ensure continuous trace generation

### Components Disappearing

**Cause:** Auto-expiration (15 minutes)

**Solution:**
- Increase traffic to services (generates more spans)
- Adjust `expireElementsAfter` in data source config (not recommended)
- Check for interrupted trace generation

### Missing Relations

**Possible Causes:**

1. **Trace context not propagated:**
   - Ensure HTTP headers or gRPC metadata includes trace context
   - Verify instrumentation libraries support propagation

2. **Spans not linked:**
   - Check parent span ID in child spans
   - Verify same trace ID across services

3. **Relation type not recognized:**
   - Check `span.kind` values (SERVER, CLIENT, PRODUCER, CONSUMER)
   - Verify `db.system` attribute for database relations

### Metrics Not Showing

**Possible Causes:**

1. **Metric binding scope mismatch:**
   - Verify component has correct labels (e.g., `stackpack:open-telemetry`)
   - Check `service.namespace` and `service.name` tags match

2. **Prometheus metrics not available:**
   - Ensure OTel Collector exports metrics
   - Verify Prometheus scraping OTel metrics

3. **Language-specific metrics:**
   - JVM metrics require `telemetry.sdk.language = "java"`
   - .NET metrics require `telemetry.sdk.language = "dotnet"`

---

## Summary

The OpenTelemetry StackPack represents a fundamentally different approach to topology creation compared to traditional StackPacks:

**Key Innovations:**
1. **Trace-Driven Topology**: Components emerge from actual runtime behavior, not configuration
2. **Zero Configuration**: No instances, no agent setup, just send traces
3. **Real-Time Discovery**: Services appear as soon as they generate traces
4. **Automatic Relationships**: Dependencies inferred from span parent-child relationships
5. **Multi-Language Support**: Extensible metric bindings for Java, .NET, and more

**Architecture Highlights:**
- Fixed Kafka topic (`sts_topo_opentelemetry_collector`)
- Auto-expiring components (15-minute TTL)
- Groovy mapping + Handlebars templating pipeline
- Prometheus-based metric bindings
- Dynamic component and relation type creation

**Best Use Cases:**
- Cloud-native microservices architectures
- Containerized applications (Kubernetes)
- Service mesh environments
- Applications requiring vendor-neutral observability
- Multi-language distributed systems

**Limitations:**
- Requires application instrumentation
- No historical topology (only active services)
- Limited infrastructure visibility (use with K8s or Agent V2 StackPacks)
- Depends on proper trace context propagation

**Integration Opportunities:**
- Kubernetes StackPack (infrastructure layer)
- StackState Agent V2 (host/process layer)
- Custom StackPacks (domain-specific extensions)

The OpenTelemetry StackPack exemplifies the next generation of observability integrations: data-driven, automatic, and deeply integrated with modern application architectures.
