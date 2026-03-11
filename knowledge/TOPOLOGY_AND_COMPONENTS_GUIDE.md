# Topology & Component Creation Guide for SUSE Observability StackPacks

A comprehensive guide to understanding and creating topology components, relations, and the full data pipeline — with a deep focus on the OpenTelemetry StackPack.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [The Data Pipeline: From Source to Topology](#2-the-data-pipeline-from-source-to-topology)
3. [Component Types: Defining What Exists](#3-component-types-defining-what-exists)
4. [Relations: How Components Connect](#4-relations-how-components-connect)
5. [Topology Inference & Identity](#5-topology-inference--identity)
6. [Layers, Domains, and Environments](#6-layers-domains-and-environments)
7. [Deep Dive: The OpenTelemetry StackPack](#7-deep-dive-the-opentelemetry-stackpack)
8. [Creating New Topology Resources: Step-by-Step](#8-creating-new-topology-resources-step-by-step)
9. [Metric Bindings & Monitors](#9-metric-bindings--monitors)
10. [Views and UI Configuration](#10-views-and-ui-configuration)
11. [Reference: Resource Types Catalog](#11-reference-resource-types-catalog)

---

## 1. Architecture Overview

SUSE Observability builds a **topology graph** — a live, interconnected map of your infrastructure and applications. This graph consists of:

- **Components** — nodes in the graph (services, pods, databases, hosts, etc.)
- **Relations** — edges connecting components (runs_on, provided-by, synchronous, etc.)
- **Layers** — vertical stacking (Services, Containers, Machines, etc.)
- **Domains** — horizontal grouping (Open Telemetry, Kubernetes cluster-X, etc.)
- **Environments** — deployment context (production, staging, etc.)

Every StackPack defines how external data is transformed into this topology graph.

### High-Level Data Flow

```
External System (OTel SDK, K8s API, Dynatrace, etc.)
        |
        v
   SUSE Observability Receiver
        |
        v
   Kafka Topic (e.g. sts_topo_opentelemetry_collector)
        |
        v
   DataSource (reads from Kafka topic)
        |
        v
   Synchronization Pipeline
        |
        +---> Component Mapping Function (Groovy)
        |         Enriches, normalizes, adds tags/properties
        |
        +---> ID Extractor Function (Groovy)
        |         Creates unique identity for merge resolution
        |
        +---> Template Function (Handlebars)
        |         Renders final Component/Relation JSON
        |
        v
   Topology Store (Components + Relations)
        |
        v
   Monitors, Metric Bindings, Views (UI)
```

---

## 2. The Data Pipeline: From Source to Topology

### 2.1 DataSource: Where Data Enters

A DataSource defines the Kafka topic and ingestion settings. Every StackPack registers at least one.

```yaml
- _type: DataSource
  name: "Open Telemetry"
  identifier: "urn:stackpack:open-telemetry:shared:data-source:opentelemetry"
  pluginId: Sts
  config:
    _type: Sts.StsTopologyDataSourceConfig
    integrationType: opentelemetry
    topic: sts_topo_opentelemetry_collector    # Kafka topic
    supportedDataTypes:
      - TOPOLOGY_ELEMENTS
    autoExpireElements: true
    expireElementsAfter: 900000                # 15 minutes in ms
  extTopology:
    _type: ExtTopology
    settings:
      _type: TopologySyncSettings
      maxBatchSize: 200
      maxBatchesPerSecond: 5
```

Key settings:
- **`topic`** — The Kafka topic to consume from. Each integration type writes to its own topic.
- **`integrationType`** — Identifies the source system (opentelemetry, kubernetes, dynatrace, etc.)
- **`autoExpireElements`** / **`expireElementsAfter`** — If data stops arriving for a component, it's automatically removed after this timeout. This keeps topology current.
- **`maxBatchSize`** / **`maxBatchesPerSecond`** — Throughput control.

### 2.2 Synchronization: The Processing Pipeline

A Sync ties a DataSource to its processing functions:

```yaml
- _type: Sync
  name: "Open Telemetry"
  identifier: "urn:stackpack:open-telemetry:shared:sync:opentelemetry"
  topologyDataQuery:
    _type: Sts.StsTopologyElementsQuery
    componentIdExtractorFunction: {{ get "urn:stackpack:common:id-extractor-function:default-function" }}
    relationIdExtractorFunction: {{ get "urn:stackpack:common:id-extractor-function:default-function" }}
  defaultComponentAction:
    _type: SyncActionCreateComponent
    mappingFunction: -11              # Reference to ComponentMappingFunction
    templateFunction: -100            # Reference to ComponentTemplateFunction
    mergeStrategy: MergePreferMine    # Keep existing data on conflict
  defaultRelationAction:
    _type: SyncActionCreateRelation
    templateFunction: -102            # Reference to RelationTemplateFunction
    mergeStrategy: MergePreferTheirs  # Accept incoming data on conflict
```

### 2.3 Component Mapping Function (Groovy)

The mapping function is the first transformation step. It receives raw `element` data and can enrich, normalize, or transform it before templating.

**What the element looks like when it arrives:**

```groovy
element.externalId    // e.g. "urn:opentelemetry:namespace/shop:service/cart-service"
element.type.name     // e.g. "service", "service_instance", "namespace"
element.data.name     // e.g. "cart-service"
element.data.tags     // e.g. ["service.namespace": "shop", "service.name": "cart-service"]
element.data.properties  // Additional metadata
element.data.version  // Version string
```

**Example — OpenTelemetry mapping function:**

```groovy
// Ensure data structures exist
if (!element.data.containsKey("tags")) {
  element.data.put("tags", [:])
}
if (!element.data.containsKey("properties")) {
  element.data.put("properties", [:])
}

// Extract namespace identifier for cross-component linking
if (element.data.tags.containsKey("service.namespace")) {
    def namespace = element.data.tags["service.namespace"]
    element.data.properties.put("namespaceIdentifier",
        "urn:opentelemetry:namespace/${namespace}".toString())
}

// Normalize component type names and build identifiers
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
    element.data.properties.put("serviceIdentifier",
        "urn:opentelemetry:namespace/${namespace}:service/${serviceName}".toString())
    break;
}

// Tag for filtering in views and queries
element.data.tags.put("stackpack", "open-telemetry")

element  // Return the modified element
```

**What the mapping function does:**
1. Normalizes type names (e.g., `service_instance` -> `service-instance`)
2. Computes cross-reference identifiers (so a service instance can link back to its service)
3. Adds the `stackpack` label for view filtering
4. Ensures all required data structures exist

### 2.4 Component Template Function (Handlebars)

After mapping, the template function renders the final Component JSON that gets stored in the topology:

```handlebars
{
  "_type": "Component",
  "name": "{{#if element.data.name}}{{ element.data.name }}{{else}}{{ element.externalId }}{{/if}}",
  "type": {{ getOrCreate
      (identifier "urn:stackpack:open-telemetry:shared" "ComponentType" element.type.name)
      (identifier "urn:system:auto" "ComponentType" element.type.name)
      (concat "Type=ComponentType;Name=" element.type.name) }},
  "layer":  {{ get "urn:stackpack:common:layer:services" }},
  "domain": {{ get "urn:stackpack:open-telemetry:shared:domain:opentelemetry" }},
  "environments": [
    {{ get "urn:stackpack:common:environment:production" }}
  ],
  "labels": [
    {{#if element.data.tags}}
    {{# join element.data.tags ","}}
        { "_type": "Label", "name": "{{key}}:{{this}}" }
    {{/ join }}
    {{/if}}
  ],
  "properties": {
    {{#if element.data.properties}}
        {{# join element.data.properties ","}}
            "{{key}}": "{{this}}"
        {{/ join }}
    {{/if}}
  }
}
```

**Key Handlebars helpers:**
- **`{{ get "urn:..." }}`** — Resolves a URN to an existing StackState object
- **`{{ getOrCreate ... }}`** — Resolves or auto-creates the object if it doesn't exist
- **`{{ identifier "prefix" "type" name }}`** — Constructs a URN identifier
- **`{{ join map "," }}`** — Iterates a map, joining entries with a separator

### 2.5 Relation Template Function

Relations follow the same pattern:

```handlebars
{
  "_type": "Relation",
  "name": "{{ element.sourceExternalId }} --> {{ element.targetExternalId }}",
  "type": {{ getOrCreate
      (identifier "urn:stackpack:open-telemetry:shared" "RelationType" element.type.name)
      (identifier "urn:system:auto" "RelationType" element.type.name)
      (concat "Type=RelationType;Name=" element.type.name) }},
  "dependencyDirection": "ONE_WAY",
  "source": {{ element.sourceId }},
  "target": {{ element.targetId }},
  "labels": [
    {{#if element.data.tags}}
    {{# join element.data.tags ","}}
        { "_type": "Label", "name": "{{key}}:{{this}}" }
    {{/ join }}
    {{/if}}
  ]
}
```

---

## 3. Component Types: Defining What Exists

A `ComponentType` defines how a category of components behaves in the UI — what fields to show, what metrics to display, what related resources to link.

### 3.1 Minimal Component Type

```yaml
- _type: "ComponentType"
  identifier: "urn:stackpack:my-stackpack:shared:component-type:my-component"
  name: "my component"
  iconbase64: "{{ include './icons/my-icon.png' 'base64' }}"
```

### 3.2 Full Component Type Structure

```yaml
- _type: "ComponentType"
  identifier: "urn:stackpack:open-telemetry:shared:component-type:service"
  name: "otel service"
  iconbase64: "{{ include './icons/service.png' 'base64' }}"
  highlights:
    _type: "ComponentTypeHighlight"
    namePlural: "services"             # Plural name for grouping

    # --- Fields shown on the component detail page ---
    fields:
      - _type: "ComponentTypeField"
        fieldId: "type"
        label:
          title: "Type"
        valueExtractor:
          _type: "ComponentTypeSource"   # Shows the component type name
        display:
          _type: "TagDisplay"

      - _type: "ComponentTypeField"
        fieldId: "health"
        label:
          title: "Health"
        valueExtractor:
          _type: "HealthSource"          # Shows health state badge
        display:
          _type: "HealthBadgeDisplay"

      - _type: "ComponentTypeField"
        fieldId: "namespace"
        label:
          title: "Otel Namespace"
        valueExtractor:
          _type: "CompositeSource"       # Combines tag + property to create a link
          sources:
            name:
              _type: "TagSource"
              tagName: "service.namespace"
            identifier:
              _type: "PropertySource"
              key: "namespaceIdentifier"
        display:
          _type: "ComponentLinkDisplay"  # Clickable link to another component

      - _type: "ComponentTypeField"
        fieldId: "labels"
        label:
          title: "Labels"
        valueExtractor:
          _type: "TagsSource"            # Shows all tags
        display:
          _type: "TagDisplay"
          singular: "label"

    # --- Which fields appear on the About section ---
    about:
      _type: "ComponentTypeAbout"
      fields: ["type", "health", "namespace", "labels"]

    # --- Events configuration ---
    events:
      _type: "ComponentTypeEvents"
      showEvents: true
      relatedResourcesTemplate: |
        (withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1"))
          and type = "otel service instance"

    # --- Related Resources (tabs in the UI) ---
    relatedResources:
      - _type: "ComponentTypeRelatedResources"
        resourceType: "service instance"
        title: "Instances of this service"
        stql: '(withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1"))
               and type = "otel service instance"'
        viewTypeIdentifier: "urn:stackpack:open-telemetry:shared:view-type:service-instance"

    # --- Metric categories shown on the component ---
    metrics:
      - _type: "ComponentTypeMetricCategory"
        name: "Traces"
        description: "Rate, Errors and Duration metrics"
        bindings:
          - "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-rate"
          - "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-error-rate"
          - "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-duration"
```

### 3.3 Value Extractors Reference

| Extractor Type | Purpose | Example Use |
|---|---|---|
| `ComponentTypeSource` | Shows the component type name | "Type" field |
| `HealthSource` | Shows health state | Health badge |
| `TagSource` | Extracts a specific tag value | `tagName: "service.namespace"` |
| `TagsSource` | Shows all tags/labels | Labels field |
| `PropertySource` | Extracts a property value | `key: "namespaceIdentifier"` |
| `CompositeSource` | Combines multiple sources | Link display (name + identifier) |

### 3.4 Display Types Reference

| Display Type | Renders As |
|---|---|
| `TagDisplay` | Colored tag badge |
| `HealthBadgeDisplay` | Health state icon (green/orange/red) |
| `ComponentLinkDisplay` | Clickable link to another component |
| `TextDisplay` | Plain text |

---

## 4. Relations: How Components Connect

### 4.1 Relation Types

Relations define how components are connected and how health propagates through the graph.

```yaml
- _type: "RelationType"
  identifier: "urn:stackpack:open-telemetry:shared:relation-type:provided-by"
  name: "provided-by"
  dependencyDirection: "ONE_WAY"
  dependencyType: HIERARCHICAL    # Structural containment
```

**Dependency Types:**

| Type | Meaning | Health Propagation | Example |
|---|---|---|---|
| `HIERARCHICAL` | Parent-child containment | Child health rolls up to parent | Service -> Service Instance |
| `CONNECTION` | Runtime dependency | Source depends on target | Service A calls Service B |
| `UNCLASSIFIED` | Informational link | No health propagation | Kubernetes Pod -> OTel Instance |

**Dependency Direction:**

| Direction | Meaning |
|---|---|
| `ONE_WAY` | Health flows from target to source |
| `BOTH` | Health flows bidirectionally |
| `NONE` | No health propagation |

### 4.2 OpenTelemetry Relation Types

| Relation | Dep. Type | Direction | Purpose |
|---|---|---|---|
| `provided-by` | HIERARCHICAL | ONE_WAY | Service Instance is provided by a Service |
| `synchronous` | CONNECTION | ONE_WAY | HTTP/gRPC call between services |
| `asynchronous` | CONNECTION | ONE_WAY | Message queue communication |
| `database` | CONNECTION | ONE_WAY | Service calls a database |
| `kubernetes-to-otel` | UNCLASSIFIED | NONE | Links K8s pod to OTel service instance |

### 4.3 Relation Patterns Across StackPacks

**Kubernetes:**
- `encloses` / `enclosed_in` — Namespace encloses Deployments
- `controls` / `creates` — Deployment controls ReplicaSet
- `scheduled_on` — Pod scheduled on Node
- `runs_on` — Container runs on Pod
- `exposes` — Service exposes Pods
- `mounts` — Pod mounts PersistentVolume

**Agent v2:**
- `runs_on` — Process runs on Host
- `connects_to` — Process connects to external API

---

## 5. Topology Inference & Identity

### 5.1 How Components Are Identified

Every component gets a unique identity through the **ID Extractor Function**. The default extractor works like this:

```groovy
externalId = element["externalId"]
type = element["typeName"].toLowerCase()
identifiers = new HashSet()

// Additional identifiers allow cross-stackpack merging
if (data.containsKey("identifiers") && data["identifiers"] instanceof List<String>) {
    identifiers.each { id -> identifiers.add(id) }
}

return Sts.createId(externalId, identifiers, type)
```

**Identity consists of three parts:**
1. **`externalId`** — Primary unique identifier from the source system (e.g., `urn:opentelemetry:namespace/shop:service/cart`)
2. **`type`** — Component type (used as part of identity scope)
3. **`identifiers`** — A set of additional URNs that enable **cross-source merging**

### 5.2 URN Naming Conventions

URN patterns are critical for topology inference. They follow this structure:

```
urn:<source>:<hierarchy>/<value>:<hierarchy>/<value>...
```

**OpenTelemetry URN patterns:**
```
urn:opentelemetry:namespace/<ns>
urn:opentelemetry:namespace/<ns>:service/<svc>
urn:opentelemetry:namespace/<ns>:service/<svc>:serviceInstance/<id>
```

**Kubernetes URN patterns:**
```
urn:kubernetes:/<cluster>:namespace/<ns>
urn:kubernetes:/<cluster>:namespace/<ns>:deployment/<name>
urn:kubernetes:/<cluster>:namespace/<ns>:pod/<name>
```

### 5.3 Merge Strategies

When two data sources report the same component (matched by identifiers), a merge strategy determines which data wins:

| Strategy | Behavior | Use Case |
|---|---|---|
| `MergePreferMine` | Incoming data wins on conflict | Component updates from primary source |
| `MergePreferTheirs` | Existing data wins on conflict | Preserving manually enriched data |

In the OTel stackpack:
- **Components** use `MergePreferMine` — the latest OTel data is authoritative
- **Relations** use `MergePreferTheirs` — existing relation metadata is preserved

### 5.4 Cross-StackPack Topology Merging

The `kubernetes-to-otel` relation type demonstrates how different StackPacks can link their topology together. When a Kubernetes Pod has an identifier that matches an OTel Service Instance, a relation is created connecting the two views.

This is powered by the **identifiers** set in `Sts.createId()`. If component A from StackPack X shares an identifier with component B from StackPack Y, they can be linked or merged.

### 5.5 Element Expiration

Components are ephemeral by default. If a source stops sending updates for a component, it is automatically removed:

```yaml
autoExpireElements: true
expireElementsAfter: 900000   # 15 minutes
```

This keeps the topology graph accurate — crashed pods disappear, scaled-down services shrink, and decommissioned hosts are cleaned up.

---

## 6. Layers, Domains, and Environments

### 6.1 Layers (Vertical Organization)

Layers stack components visually from high-level abstractions down to infrastructure:

| Layer | Order | Examples |
|---|---|---|
| Users | 2000 | End users, clients |
| Business Processes | 3000 | Business workflows |
| Applications | 4000 | Application instances |
| Services | 7000 | OTel services, K8s services |
| Containers | 9000 | Docker containers, pods |
| Processes | 10000 | OS processes |
| Databases | 12000 | Database instances |
| Machines | 13000 | VMs, bare metal hosts |
| Networking | 15000 | Load balancers, firewalls |

The OTel StackPack places all its components in the **Services** layer.

### 6.2 Domains (Horizontal Organization)

Domains group components by source or ownership:

```yaml
- _type: Domain
  name: "Open Telemetry"
  identifier: "urn:stackpack:open-telemetry:shared:domain:opentelemetry"
  description: "Open Telemetry services and resources"
```

### 6.3 Environments

Environments classify deployment context. The OTel StackPack defaults to `production`:

```handlebars
"environments": [
    {{ get "urn:stackpack:common:environment:production" }}
]
```

---

## 7. Deep Dive: The OpenTelemetry StackPack

### 7.1 Where Does the Data Come From?

The OpenTelemetry StackPack consumes data that originates from **OpenTelemetry-instrumented applications**. The flow is:

```
Your Application
  |-- OTel SDK (Java, .NET, Python, Go, Node.js, etc.)
  |     Automatically instruments your code
  |     Collects: traces, metrics, resource attributes
  |
  v
OpenTelemetry Collector (optional)
  |     Receives, processes, and exports telemetry
  |
  v
SUSE Observability Receiver
  |     Accepts OTLP data (gRPC/HTTP)
  |     Converts to internal topology elements
  |
  v
Kafka Topic: sts_topo_opentelemetry_collector
  |     Buffers topology elements
  |
  v
OTel StackPack Synchronization
      Reads from Kafka, transforms, stores topology
```

### 7.2 What Type of Data?

The OTel StackPack processes two categories:

**A. Topology Elements (from resource attributes)**

OTel resource attributes like `service.name`, `service.namespace`, `service.instance.id` are transformed into topology components. The Receiver converts these into `ExtTopoElement` objects:

```
ExtTopoElement:
  externalId: "urn:opentelemetry:namespace/shop:service/cart-service"
  type.name: "service"
  data:
    name: "cart-service"
    tags:
      service.name: "cart-service"
      service.namespace: "shop"
      service.instance.id: "cart-abc123"
      telemetry.sdk.language: "java"
    properties: {}
    version: "1.0.0"
```

**B. Metrics (from spans and runtime instrumentation)**

The Receiver also generates Prometheus-format metrics from OTel spans:

| Metric | Source | Description |
|---|---|---|
| `otel_span_calls_total` | Trace spans | Counter of span invocations, labeled by `service_name`, `service_namespace`, `span_kind`, `status_code` |
| `otel_span_duration_milliseconds_bucket` | Trace spans | Histogram of span durations for percentile calculations |
| `traces_service_graph_*` | Service graph connector | Pre-computed service dependency metrics |
| `process.runtime.jvm.*` | JVM runtime metrics | GC, memory, thread counts (Java apps) |
| `process.runtime.dotnet.*` | .NET runtime metrics | GC collections, memory allocation (.NET apps) |

### 7.3 Component Hierarchy

The OTel StackPack creates this topology structure:

```
Service Namespace
  |
  |-- provided-by --> Service
  |                     |
  |                     |-- provided-by --> Service Instance
  |                     |                     |
  |                     |                     |-- kubernetes-to-otel --> Pod (K8s)
  |                     |
  |                     |-- synchronous ----> Service (another)
  |                     |-- asynchronous ---> Service (another)
  |                     |-- database -------> Database
  |
  |-- provided-by --> Service Instance (directly)
```

### 7.4 The Five Component Types

| Component Type | Identifier | Description |
|---|---|---|
| `service namespace (otel)` | `urn:stackpack:open-telemetry:shared:component-type:service-namespace` | Logical grouping of services (from `service.namespace` resource attribute) |
| `otel service` | `urn:stackpack:open-telemetry:shared:component-type:service` | A service identified by name (from `service.name`) |
| `otel service instance` | `urn:stackpack:open-telemetry:shared:component-type:service-instance` | A specific running instance of a service (from `service.instance.id`) |
| `database` | `urn:stackpack:open-telemetry:shared:component-type:database` | A database discovered through span attributes |
| `pod` | `urn:stackpack:open-telemetry:shared:component-type:pod` | Kubernetes pod (stub for cross-stackpack linking) |

### 7.5 How Services Are Discovered

Services are **automatically discovered from trace data**. When an application instrumented with OTel sends spans:

1. The **resource attributes** (`service.name`, `service.namespace`, `service.instance.id`) identify components
2. The **span attributes** (`db.system`, `peer.service`, `http.url`) identify dependencies
3. The **span kind** (`SERVER`, `CLIENT`, `CONSUMER`, `PRODUCER`) determines relation directionality
4. The Receiver builds topology elements and publishes them to Kafka

No manual registration is needed — the topology emerges from the trace data.

### 7.6 How Relations Are Discovered

Relations between services come from the **service graph**, built by analyzing client/server span pairs:

- A `CLIENT` span from Service A calling Service B creates a `synchronous` relation A -> B
- A `PRODUCER` span sending to a queue creates an `asynchronous` relation
- A `CLIENT` span with `db.system` attribute creates a `database` relation to the database component
- The `provided-by` HIERARCHICAL relation connects instances to their parent services

### 7.7 Monitors

The OTel StackPack includes five monitors that automatically attach to components via URN templates:

```yaml
- _type: Monitor
  name: Span error ratio for Open Telemetry services
  identifier: urn:stackpack:open-telemetry:shared:monitor:otel-service-span-error-ratio
  function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
  intervalSeconds: 30
  status: ENABLED
  arguments:
    comparator: GT
    failureState: DEVIATING
    threshold: 5
    metric:
      query: >
        sum by(service_namespace, service_name)(
          rate(otel_span_calls_total{
            status_code="STATUS_CODE_ERROR",
            span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"
          }[5m]) or (present_over_time(
            otel_span_calls_total{span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}[5m]) - 1)
        ) / sum by(service_namespace, service_name)(
          rate(otel_span_calls_total{
            span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"
          }[5m])
        ) * 100
      aliasTemplate: Error ratio (errors/total)
      unit: percent
    urnTemplate: "urn:opentelemetry:namespace/${service_namespace}:service/${service_name}"
```

**How `urnTemplate` works:** The monitor query returns metrics with labels like `service_namespace=shop` and `service_name=cart`. The `urnTemplate` uses these labels to construct a URN that matches a component's externalId, automatically attaching the health state to the right component.

---

## 8. Creating New Topology Resources: Step-by-Step

### 8.1 Adding a New Component Type

**Step 1: Create the type definition file**

Create `provisioning/templates/component-types/my-component.sty`:

```yaml
- _type: "ComponentType"
  identifier: "urn:stackpack:my-stackpack:shared:component-type:my-component"
  name: "my component"
  iconbase64: "{{ include './icons/my-component.png' 'base64' }}"
  highlights:
    _type: "ComponentTypeHighlight"
    namePlural: "my components"
    fields:
      - _type: "ComponentTypeField"
        fieldId: "type"
        label:
          title: "Type"
        valueExtractor:
          _type: "ComponentTypeSource"
        display:
          _type: "TagDisplay"
      - _type: "ComponentTypeField"
        fieldId: "health"
        label:
          title: "Health"
        valueExtractor:
          _type: "HealthSource"
        display:
          _type: "HealthBadgeDisplay"
    about:
      _type: "ComponentTypeAbout"
      fields: ["type", "health"]
    events:
      _type: "ComponentTypeEvents"
      showEvents: true
    metrics: []
```

**Step 2: Include it in the main template**

In your main `.sty` file, include the new component type:

```yaml
{{ include "./templates/component-types/my-component.sty" }}
```

**Step 3: Handle it in the mapping function**

In your component mapping Groovy script, handle the new type:

```groovy
switch (element.type.name) {
  case "my_component":
  case "my-component":
    element.type.name = "my-component"
    // Add any computed properties
    break;
}
```

### 8.2 Adding a New Relation Type

```yaml
- _type: "RelationType"
  identifier: "urn:stackpack:my-stackpack:shared:relation-type:depends-on"
  name: "depends-on"
  dependencyDirection: "ONE_WAY"
  dependencyType: CONNECTION
```

### 8.3 Adding Related Resources to a Component Type

Related resources create tabs in the component detail view that show linked components:

```yaml
relatedResources:
  - _type: "ComponentTypeRelatedResources"
    resourceType: "service instance"
    title: "Running Instances"
    stql: '(withNeighborsOf(direction = "down",
            components = (id = "{COMPONENT_ID}"), levels = "1"))
            and type = "otel service instance"'
    viewTypeIdentifier: "urn:stackpack:my-stackpack:shared:view-type:instance"
```

**STQL patterns for related resources:**

```
# Direct neighbors (1 hop down)
(withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1"))
  and type = "my type"

# Components sharing a label
type = "my type" AND label in ("my-label:{COMPONENT_NAME}")

# 2-hop traversal (neighbors of neighbors)
(withNeighborsOf(direction = "up",
  components = (withNeighborsOf(direction = "both",
    components = (id = "{COMPONENT_ID}"), levels = "1")
    and type = "intermediate type"),
  levels = "1")
  and type = "target type")
```

### 8.4 Creating a Complete New Resource (End-to-End Checklist)

1. **Define the ComponentType** in a `.sty` file under `component-types/`
2. **Define any new RelationTypes** in `relation-types.sty`
3. **Update the component mapping function** to handle the new type name
4. **Verify the template function** handles the new type (usually automatic via `getOrCreate`)
5. **Add metric bindings** if the component has associated metrics
6. **Add monitors** if the component should have health checks
7. **Create a QueryView** to make the component browsable in the UI
8. **Create a ViewType** to define the table columns for the overview
9. **Add an icon** (PNG for component type, SVG for views)
10. **Include everything** in the main `.sty` template file
11. **Test** by deploying and verifying topology appears

---

## 9. Metric Bindings & Monitors

### 9.1 Metric Binding Structure

Metric bindings attach PromQL queries to components. The `scope` field (STQL) determines which components get the binding.

```yaml
- _type: MetricBinding
  identifier: urn:stackpack:open-telemetry:shared:metric-binding:service-instance-spans-rate
  name: Span rate
  chartType: line
  unit: cps                    # calls per second
  enabled: true
  priority: MEDIUM
  scope: (label = "stackpack:open-telemetry" and type = "otel service instance")
  queries:
    - expression: >
        sum(rate(otel_span_calls_total{
          service_namespace="${tags.service.namespace}",
          service_name="${tags.service.name}",
          service_instance_id="${tags.service.instance.id}"
        }[${__rate_interval}])) by (span_kind)
      alias: 'All ${span_kind}'
  layout:
    metricPerspective:
      tab: Traces Performance
      section: Spans
```

**Placeholder variables in queries:**
- `${tags.<tag_name>}` — Resolves to the component's tag value
- `${name}` — Resolves to the component's name
- `${__rate_interval}` — System-managed rate interval
- `${span_kind}` — PromQL label used in `by()` clause (for legend)

**Layout options:**
- `metricPerspective` — Shows in the Metrics tab, organized by tab/section
- `componentSummary` — Shows as a sparkline on the component card (use `weight` for ordering)

### 9.2 Monitor Structure

```yaml
- _type: Monitor
  identifier: urn:stackpack:my-stackpack:shared:monitor:my-monitor
  name: My Health Monitor
  description: Checks if the error rate exceeds threshold
  function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
  intervalSeconds: 30
  status: ENABLED
  tags: ["service", "errors"]
  arguments:
    comparator: GT             # GT, GTE, LT, LTE, EQ
    failureState: DEVIATING    # DEVIATING or CRITICAL
    threshold: 5
    metric:
      query: '<PromQL query>'
      aliasTemplate: "Description"
      unit: percent
    urnTemplate: "urn:opentelemetry:namespace/${service_namespace}:service/${service_name}"
  remediationHint: "{{ include './monitors/my-monitor/remediation-hint.md.hbs' 'identity' }}"
```

**Common monitor functions:**
- `threshold` — Compare metric value against a static threshold
- `topological-threshold` — Dynamic threshold based on peer components
- `health-aggregator` — Aggregate child component health states

---

## 10. Views and UI Configuration

### 10.1 QueryView (Browsable View)

```yaml
- _type: QueryView
  name: Services
  description: Open Telemetry Services
  identifier: urn:stackpack:open-telemetry:shared:query-view:services
  query: (label IN ("stackpack:open-telemetry") AND type IN ("otel service"))
  viewType: urn:stackpack:open-telemetry:shared:view-type:service
  minimumGroupSize: 8
  groupedByDomains: true
  groupedByLayers: false
  connectedComponents: true
  groupingEnabled: true
  autoGrouping: true
  flags:
    - HideFromViewsOverview
    - NotUnlockable
    - DisableEventHandlers
```

### 10.2 ViewType (Table Layout)

```yaml
- _type: "ViewType"
  name: "Open Telemetry services view definition"
  identifier: "urn:stackpack:open-telemetry:shared:view-type:service"
  iconbase64: "{{ include './icons-svg/services.svg' 'base64' }}"
  filters:
    - _type: "TopologyFilters"
      tabs: ["EVENTS", "TRACES"]
  flags: ["NoTopologyFilters"]
  overview:
    columns:
      - _type: "ViewTypeTableColHealth"
      - _type: "ViewTypeTableColName"
        title: "Service"
      - _type: "ViewTypeTableColComponentLink"
        title: "Namespace"
        labelPrefix: "service.namespace"
        pathToIdentifier: ["properties", "namespaceIdentifier"]
        width: 200
      - _type: "ViewTypeTableColMetricBinding"
        title: "Span error %"
        metricBindingIdentifier: "urn:stackpack:...:service-spans-error-percent-summary"
        width: 145
      - _type: "ViewTypeTableColText"
        title: "Language"
        path: ["tags", "telemetry.sdk.language"]
        width: 120
```

**Column types:**

| Type | Purpose |
|---|---|
| `ViewTypeTableColHealth` | Health state indicator |
| `ViewTypeTableColName` | Component name (always include) |
| `ViewTypeTableColComponentLink` | Clickable link to a related component |
| `ViewTypeTableColMetricBinding` | Inline sparkline from a metric binding |
| `ViewTypeTableColText` | Static text from a tag or property path |

### 10.3 Trace Bindings

Connect components to their distributed traces:

```yaml
- _type: TraceBinding
  name: Traces for Open-telemetry services
  identifier: urn:stackpack:open-telemetry:shared:trace-binding:service
  filter:
    attributes:
      service.namespace: ["${tags.service.namespace}"]
      service.name: ["${name}"]
  scope: (label = "stackpack:open-telemetry" and type = "otel service")
```

### 10.4 Span-to-Component Bindings

When viewing a trace, link individual spans back to their topology component:

```yaml
- _type: SpanToComponentBinding
  name: Open-telemetry span binding to service instance
  identifier: urn:stackpack:open-telemetry:shared:span-to-component-binding:service-instance
  urnTemplate: "urn:opentelemetry:namespace/${resource.service.namespace}:service/${resource.service.name}:serviceInstance/${resource.service.instance.id}"
```

---

## 11. Reference: Resource Types Catalog

### All STY/STJ Resource Types

| `_type` | Purpose | Key Fields |
|---|---|---|
| `DataSource` | Ingestion endpoint | `config`, `pluginId`, `topic` |
| `Sync` | Processing pipeline | `componentActions`, `relationActions`, `topologyDataQuery` |
| `ComponentMappingFunction` | Groovy data enrichment | `script`, `parameters` |
| `ComponentTemplateFunction` | Handlebars JSON rendering | `handlebarsTemplate` |
| `RelationTemplateFunction` | Handlebars relation rendering | `handlebarsTemplate` |
| `ComponentType` | UI type definition | `highlights`, `identifier`, `iconbase64` |
| `RelationType` | Connection definition | `dependencyDirection`, `dependencyType` |
| `Domain` | Horizontal grouping | `name`, `identifier` |
| `Layer` | Vertical stacking | `name`, `order` |
| `Environment` | Deployment context | `name`, `identifier` |
| `QueryView` | Browsable topology view | `query` (STQL), `viewType` |
| `ViewType` | Table column layout | `overview.columns`, `filters` |
| `MetricBinding` | PromQL -> Component chart | `queries`, `scope`, `layout` |
| `Monitor` | Health check rule | `function`, `arguments`, `urnTemplate` |
| `TraceBinding` | Trace -> Component link | `filter`, `scope` |
| `SpanToComponentBinding` | Span -> Component link | `urnTemplate` |
| `MainMenuGroup` | UI navigation | `views` |

### Component Types Across StackPacks

| StackPack | Component Types |
|---|---|
| **OpenTelemetry** | service namespace, otel service, otel service instance, database, pod |
| **Kubernetes** | node, pod, container, service, deployment, daemonset, statefulset, replicaset, job, cronjob, namespace, persistent-volume, ingress, configmap, secret |
| **Agent v2** | host, process, container, endpoint |
| **Dynatrace** | application, host, process, service, custom device, synthetic monitor |
| **Static Topology** | Any custom type (dynamically created from CSV data) |

### Common Layers (from `common` StackPack)

```
Blueprints (1000) > Users (2000) > Business Processes (3000)
> Applications (4000) > App Load Balancers (5000) > Uncategorized (6000)
> Services (7000) > Serverless (8000) > Containers (9000)
> Processes (10000) > Messaging (11000) > Databases (12000)
> Machines (13000) > Storage (14000) > Networking (15000)
> Hardware (16000) > Locations (17000)
```

---

## Quick Reference: File Locations

For the OpenTelemetry StackPack, all source files are under:
`stackpacks/open-telemetry/src/main/stackpack/`

```
stackpack.conf                                    # Metadata & configuration
provisioning/
  OpenTelemetryProvision.groovy                   # Entry point
  templates/
    open-telemetry.sty                            # Main template (includes everything)
    sync/
      synchronization.sty                         # DataSource + Sync definition
      component-mapping-function.groovy           # Groovy mapping logic
      component-template.json.handlebars          # Component JSON template
      relation-template.json.handlebars           # Relation JSON template
    component-types/
      services.sty                                # otel service type + view + trace binding
      service-instances.sty                       # otel service instance type + view
      service-namespaces.sty                      # service namespace type + view
      database.sty                                # database type + view
      pod.sty                                     # pod type (stub)
    relation-types.sty                            # All relation type definitions
    domains.sty                                   # Domain definition
    main-menu.sty                                 # Navigation menu
    metric-bindings/
      metric-bindings-traces.sty                  # Span rate/error/duration metrics
      metric-bindings-otel-jvm-memory.sty         # JVM memory & GC metrics
      metric-bindings-otel-dotnet-gc.sty          # .NET runtime metrics
    monitors/
      service-span-duration/monitor.sty           # Service span duration monitor
      service-span-error-ratio/monitor.sty        # Service error ratio monitor
      service-instance-span-duration/monitor.sty  # Instance span duration monitor
      service-instance-span-error-ratio/monitor.sty
      database-span-duration/monitor.sty          # Database span duration monitor
```
