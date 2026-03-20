# ComponentType Definition Guide

**Comprehensive guide for defining ComponentTypes in StackState StackPacks**

## Table of Contents
1. [Overview](#overview)
2. [Basic Structure](#basic-structure)
3. [Core Fields](#core-fields)
4. [Highlights Configuration](#highlights-configuration)
5. [Field Definitions](#field-definitions)
6. [Value Extractors](#value-extractors)
7. [Display Types](#display-types)
8. [Events Configuration](#events-configuration)
9. [Logs and Status](#logs-and-status)
10. [External Component Integration](#external-component-integration)
11. [Related Resources](#related-resources)
12. [Metrics Integration](#metrics-integration)
13. [Traces Integration](#traces-integration)
14. [Best Practices](#best-practices)
15. [Complete Examples](#complete-examples)

---

## Overview

A **ComponentType** defines how components of a specific type are displayed, queried, and interact with other StackState features like metrics, events, logs, and traces. ComponentTypes are the foundation of the StackState topology visualization and component detail views.

ComponentTypes are typically defined in `.sty` (StackState YAML) files and can use Handlebars templating.

---

## Basic Structure

### Minimal ComponentType

```yaml
- _type: "ComponentType"
  iconbase64: "{{ include "./icons/service.png" "base64" }}"
  identifier: "urn:stackpack:my-stackpack:shared:component-type:service"
  name: "service"
```

### Full ComponentType Structure

```yaml
- _type: "ComponentType"
  iconbase64: "{{ include "./icons/my-icon.png" "base64" }}"
  identifier: "urn:stackpack:my-stackpack:shared:component-type:my-type"
  name: "my-component-type"
  description: "Description of this component type"
  ownedBy: "urn:stackpack:my-stackpack"
  highlights:
    _type: "ComponentTypeHighlight"
    # ... highlights configuration
```

---

## Core Fields

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `_type` | String | Always `"ComponentType"` | `"ComponentType"` |
| `identifier` | URN String | Unique identifier for this component type | `"urn:stackpack:open-telemetry:shared:component-type:service"` |
| `name` | String | Component type name (used in queries and display) | `"otel service"` |
| `iconbase64` | Base64 String | Base64-encoded icon image | `"{{ include "./icons/service.png" "base64" }}"` |

### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `description` | String | Human-readable description | `"Kubernetes Pod component"` |
| `ownedBy` | URN String | StackPack that owns this type | `"urn:stackpack:kubernetes-v2"` |
| `id` | Integer | Internal ID (rarely used, auto-generated) | `-101` |

### URN Format

ComponentType identifiers follow this pattern:
```
urn:stackpack:<stackpack-name>:[instance-id:]component-type:<type-name>
```

- **shared**: Use `shared` for component types that are shared across all instances
- **instance-specific**: Use actual instance ID for instance-specific types

**Examples:**
- `urn:stackpack:kubernetes-v2:shared:component-type:pod`
- `urn:stackpack:open-telemetry:shared:component-type:service`
- `urn:stackpack:common:component-type:application`

---

## Highlights Configuration

The `highlights` section defines the complete UI and behavior configuration for the component type.

### Highlights Types

- **`ComponentTypeHighlight`**: Standard highlights (most common)
- **`ComponentTypeExt`**: Extended highlights with additional features

### Basic Structure

```yaml
highlights:
  _type: "ComponentTypeHighlight"
  namePlural: "services"
  fields: []
  about: {}
  events: {}
  showLogs: false
  showLastChange: false
  externalComponent: {}
  relatedResources: []
  metrics: []
```

### namePlural

The plural name used in UI displays and tables.

```yaml
namePlural: "pods"        # For "pod" type
namePlural: "services"    # For "service" type
namePlural: "databases"   # For "database" type
```

---

## Field Definitions

Fields define what information is displayed in the component detail view, tables, and summaries.

### ComponentTypeField Structure

```yaml
- _type: "ComponentTypeField"
  fieldId: "unique-field-id"
  label:
    title: "Display Name"
    helpBubbleText: "Optional help text"  # Optional
  valueExtractor:
    _type: "<ExtractorType>"
    # ... extractor-specific properties
  display:
    _type: "<DisplayType>"
    # ... display-specific properties
```

### Field Array Example

```yaml
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
```

### Common Field IDs

Standard field IDs used across StackPacks:

- **`type`**: Component type (always use `ComponentTypeSource`)
- **`health`**: Component health state (always use `HealthSource`)
- **`labels`**: Component tags/labels (use `TagsSource`)
- **`age`**: Component age from creation timestamp
- **`namespace`**: Kubernetes namespace
- **`cluster`**: Kubernetes cluster
- **Custom fields**: Any property from your component data

---

## Value Extractors

Value extractors specify where to get the data for a field.

### 1. ComponentTypeSource

Extracts the component type itself.

```yaml
valueExtractor:
  _type: "ComponentTypeSource"
```

**Usage:** Always use for the `type` field.

---

### 2. HealthSource

Extracts the component's health state.

```yaml
valueExtractor:
  _type: "HealthSource"
```

**Usage:** Always use for the `health` field.

---

### 3. PropertySource

Extracts a value from component properties.

```yaml
valueExtractor:
  _type: "PropertySource"
  key: "propertyName"
  defaultValue: "N/A"  # Optional
```

**Properties:**
- `key`: The property name to extract
- `defaultValue`: Value to use if property doesn't exist (optional)

**Examples:**

```yaml
# Extract pod phase
valueExtractor:
  _type: "PropertySource"
  key: "podPhase"
  defaultValue: "UNKNOWN"

# Extract creation timestamp
valueExtractor:
  _type: "PropertySource"
  key: "creationTimestamp"

# Extract IP address
valueExtractor:
  _type: "PropertySource"
  key: "podIP"
```

---

### 4. TagSource

Extracts a value from component tags.

```yaml
valueExtractor:
  _type: "TagSource"
  tagName: "tag-name"
```

**Properties:**
- `tagName`: The tag name to extract

**Examples:**

```yaml
# Extract namespace tag
valueExtractor:
  _type: "TagSource"
  tagName: "namespace"

# Extract cluster name tag
valueExtractor:
  _type: "TagSource"
  tagName: "cluster-name"

# Extract service namespace
valueExtractor:
  _type: "TagSource"
  tagName: "service.namespace"
```

---

### 5. CompositeSource

Combines multiple sources (typically name + identifier for component links).

```yaml
valueExtractor:
  _type: "CompositeSource"
  sources:
    name:
      _type: "<SourceType>"
      # ... source configuration
    identifier:
      _type: "<SourceType>"
      # ... source configuration
```

**Properties:**
- `sources`: Object containing named sources
  - `name`: Source for the display name
  - `identifier`: Source for the component identifier (for links)

**Examples:**

```yaml
# Namespace link (tag for name, property for identifier)
valueExtractor:
  _type: "CompositeSource"
  sources:
    name:
      _type: "TagSource"
      tagName: "namespace"
    identifier:
      _type: "PropertySource"
      key: "namespaceIdentifier"

# Owner link (both from properties)
valueExtractor:
  _type: "CompositeSource"
  sources:
    name:
      _type: "PropertySource"
      key: "ownerName"
    identifier:
      _type: "PropertySource"
      key: "ownerIdentifier"

# Service link (both from tags)
valueExtractor:
  _type: "CompositeSource"
  sources:
    name:
      _type: "TagSource"
      tagName: "service.name"
    identifier:
      _type: "PropertySource"
      key: "serviceIdentifier"
```

**Usage with ComponentLinkDisplay:**
CompositeSource is almost always paired with `ComponentLinkDisplay` to create clickable links to related components.

---

### 6. TagsSource

Extracts all tags from the component.

```yaml
valueExtractor:
  _type: "TagsSource"
```

**Usage:** Used for displaying all labels/tags, typically with `TagDisplay`.

---

### 7. ReadyStatusSource

Extracts ready status information (used for Kubernetes pods/containers).

```yaml
valueExtractor:
  _type: "CompositeSource"
  sources:
    status:
      _type: "PropertySource"
      key: "readyContainersStatus"
    ready:
      _type: "PropertySource"
      key: "readyContainers"
    total:
      _type: "PropertySource"
      key: "totalContainers"
```

**Usage:** Paired with `ReadyStatusDisplay` to show "2/3" ready indicators.

---

## Display Types

Display types control how extracted values are rendered in the UI.

### 1. TagDisplay

Displays value(s) as tag pills/badges.

```yaml
display:
  _type: "TagDisplay"
  singular: "label"  # Optional: singular form for labels
```

**Properties:**
- `singular`: Singular form of the label (optional)

**Used with:**
- `ComponentTypeSource` (shows component type as tag)
- `TagsSource` (shows all tags)
- Single `TagSource` or `PropertySource` (shows as tag)

**Example:**
```yaml
- _type: "ComponentTypeField"
  fieldId: "labels"
  label:
    title: "Labels"
  valueExtractor:
    _type: "TagsSource"
  display:
    _type: "TagDisplay"
    singular: "label"
```

---

### 2. HealthBadgeDisplay

Displays health state as a colored badge.

```yaml
display:
  _type: "HealthBadgeDisplay"
```

**Used with:** `HealthSource` only

**Example:**
```yaml
- _type: "ComponentTypeField"
  fieldId: "health"
  label:
    title: "Health"
  valueExtractor:
    _type: "HealthSource"
  display:
    _type: "HealthBadgeDisplay"
```

---

### 3. TextDisplay

Displays value as plain text.

```yaml
display:
  _type: "TextDisplay"
```

**Used with:**
- `PropertySource` (for text values)
- Simple values like IP addresses, phases, counts

**Example:**
```yaml
- _type: "ComponentTypeField"
  fieldId: "phase"
  label:
    title: "Phase"
  valueExtractor:
    _type: "PropertySource"
    key: "podPhase"
    defaultValue: "UNKNOWN"
  display:
    _type: "TextDisplay"
```

---

### 4. DurationDisplay

Displays timestamps as relative durations (e.g., "2 hours ago", "3 days").

```yaml
display:
  _type: "DurationDisplay"
```

**Used with:** `PropertySource` containing timestamp values

**Example:**
```yaml
- _type: "ComponentTypeField"
  fieldId: "age"
  label:
    title: "Age"
    helpBubbleText: "This is the creation time relative to the current time of the view"
  valueExtractor:
    _type: "PropertySource"
    key: "creationTimestamp"
  display:
    _type: "DurationDisplay"
```

---

### 5. ComponentLinkDisplay

Displays as a clickable link to another component.

```yaml
display:
  _type: "ComponentLinkDisplay"
```

**Used with:** `CompositeSource` containing `name` and `identifier`

**Example:**
```yaml
- _type: "ComponentTypeField"
  fieldId: "namespace"
  label:
    title: "Namespace"
  valueExtractor:
    _type: "CompositeSource"
    sources:
      name:
        _type: "TagSource"
        tagName: "namespace"
      identifier:
        _type: "PropertySource"
        key: "namespaceIdentifier"
  display:
    _type: "ComponentLinkDisplay"
```

---

### 6. ReadyStatusDisplay

Displays ready/total status (e.g., "2/3 ready").

```yaml
display:
  _type: "ReadyStatusDisplay"
```

**Used with:** `CompositeSource` containing `status`, `ready`, and `total`

**Example:**
```yaml
- _type: "ComponentTypeField"
  fieldId: "readyContainers"
  label:
    title: "Ready containers"
  valueExtractor:
    _type: "CompositeSource"
    sources:
      status:
        _type: "PropertySource"
        key: "readyContainersStatus"
      ready:
        _type: "PropertySource"
        key: "readyContainers"
      total:
        _type: "PropertySource"
        key: "totalContainers"
  display:
    _type: "ReadyStatusDisplay"
```

---

## About Configuration

The `about` section specifies which fields appear in the "About" tab of the component detail view.

```yaml
about:
  _type: "ComponentTypeAbout"
  fields: ["type", "health", "namespace", "labels"]
```

**Properties:**
- `fields`: Array of field IDs (must match `fieldId` from the `fields` array)

**Best Practices:**
- Always include `type` and `health` first
- Add contextual fields relevant to the component
- Keep the list concise (5-10 fields typically)

**Example:**
```yaml
about:
  _type: "ComponentTypeAbout"
  fields: ["type", "health", "age", "serviceType", "clusterIP", "namespace", "cluster", "labels"]
```

---

## Events Configuration

Controls how events are displayed and filtered for components of this type.

### Structure

```yaml
events:
  _type: "ComponentTypeEvents"
  showEvents: true
  relatedResourcesTemplate: "<STQL query template>"
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `showEvents` | Boolean | Enable/disable events display |
| `relatedResourcesTemplate` | STQL String | Query template for filtering related events |

### STQL Query Templates

Templates use special placeholders:
- `{COMPONENT_ID}`: Replaced with the component's ID
- `{COMPONENT_NAME}`: Replaced with the component's name
- `{COMPONENT_PREDICATE}`: Replaced with component predicate
- `{CLUSTER_NAME}`: Custom placeholder (cluster name)

### Examples

#### Simple: Show events for this component only

```yaml
events:
  _type: "ComponentTypeEvents"
  showEvents: true
```

#### Show events for component and related resources

```yaml
events:
  _type: "ComponentTypeEvents"
  showEvents: true
  relatedResourcesTemplate: |
    (withNeighborsOf(direction = "up", components = (id = "{COMPONENT_ID}"), levels = "3")
     AND type IN ("pod", "deployment", "daemonset", "replicaset", "service", "statefulset"))
    OR id = "{COMPONENT_ID}"
```

#### Kubernetes service example

```yaml
events:
  _type: "ComponentTypeEvents"
  showEvents: true
  relatedResourcesTemplate: |
    (
        withNeighborsOf(direction = "both", components = (
            withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1")
            AND type IN ("pod")
        ), levels = "2")
        AND type IN ("pod", "deployment", "statefulset", "daemonset", "secret", "configmap")
    ) OR id = "{COMPONENT_ID}"
```

#### Cluster-based filtering

```yaml
events:
  _type: "ComponentTypeEvents"
  showEvents: true
  relatedResourcesTemplate: 'type IN ("node", "cluster", "persistent-volume") AND label IN ("cluster-name:{CLUSTER_NAME}")'
```

### Disable Events

```yaml
events:
  _type: "ComponentTypeEvents"
  showEvents: false
```

---

## Logs and Status

### Show Logs

Enable log streaming for this component type.

```yaml
showLogs: true   # Enable logs tab
showLogs: false  # Disable logs tab (default)
```

**When to enable:**
- Components that generate logs (pods, containers)
- Components with log collection configured

**Example (Kubernetes Pod):**
```yaml
showLogs: true  # Pods have logs
```

**Example (Kubernetes Service):**
```yaml
showLogs: false  # Services don't have direct logs
```

---

### Show Last Change

Display the last change timestamp for the component.

```yaml
showLastChange: true   # Show last change info
showLastChange: false  # Hide last change info (default)
```

**When to enable:**
- Components that change frequently
- When tracking component updates is important

---

## External Component Integration

Configure integration with external systems (original Kubernetes objects, external APIs, etc.).

### Structure

```yaml
externalComponent:
  _type: "ComponentTypeExternalComponent"
  showConfiguration: true
  showStatus: true
  externalIdSelector: "^urn:kubernetes:"
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `showConfiguration` | Boolean | Show configuration/manifest from external system |
| `showStatus` | Boolean | Show status from external system |
| `externalIdSelector` | Regex String | Pattern to match external IDs |

### External ID Selector Patterns

The `externalIdSelector` is a regex pattern that matches component external IDs.

**Common Patterns:**

```yaml
# Kubernetes components
externalIdSelector: "^urn:kubernetes:"

# OpenTelemetry components
externalIdSelector: "^urn:open-telemetry:"

# Process components
externalIdSelector: "^urn:process:"

# Container components
externalIdSelector: "^urn:container:"

# Empty (no external integration)
externalIdSelector: ""
```

### Examples

#### Full external integration (Kubernetes)

```yaml
externalComponent:
  _type: "ComponentTypeExternalComponent"
  showConfiguration: true
  showStatus: true
  externalIdSelector: "^urn:kubernetes:"
```

#### Minimal external integration

```yaml
externalComponent:
  _type: "ComponentTypeExternalComponent"
  showConfiguration: false
  showStatus: false
  externalIdSelector: "^urn:open-telemetry:"
```

#### No external integration

```yaml
externalComponent:
  _type: "ComponentTypeExternalComponent"
  showConfiguration: false
  showStatus: false
  externalIdSelector: ""
```

---

## Related Resources

Define queries to find and display related components.

### Structure

```yaml
relatedResources:
  - _type: "ComponentTypeRelatedResources"
    resourceType: "pod"
    title: "Pods"
    stql: 'type = "pod" AND label in ("namespace:{COMPONENT_NAME}")'
    viewTypeIdentifier: "urn:stackpack:k8s-common-v2:shared:view-type:pod"
```

### Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `resourceType` | String | Yes | Type of related resource |
| `title` | String | Yes | Display title in UI |
| `stql` | STQL String | Yes | Query to find related resources |
| `viewTypeIdentifier` | URN String | No | Optional view type for the related resources |

### STQL Query Placeholders

- `{COMPONENT_ID}`: The component's identifier
- `{COMPONENT_NAME}`: The component's name
- Custom properties can be referenced in queries

### Examples

#### Direct neighbors (1 level)

```yaml
- _type: "ComponentTypeRelatedResources"
  resourceType: "pod"
  title: "Pods of this service"
  stql: '(withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1")) and type = "pod"'
  viewTypeIdentifier: "urn:stackpack:k8s-common-v2:shared:view-type:pod"
```

#### Multi-level traversal

```yaml
- _type: "ComponentTypeRelatedResources"
  resourceType: "service"
  title: "Related services"
  stql: '(withNeighborsOf(direction = "up", components = (withNeighborsOf(direction = "both", components = (withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "3") and type = "process"), levels = "1") and type = "process") , levels = "3") and type = "service"'
  viewTypeIdentifier: "urn:stackpack:k8s-common-v2:shared:view-type:service"
```

#### Label-based filtering

```yaml
- _type: "ComponentTypeRelatedResources"
  resourceType: "pod"
  title: "Pods"
  stql: 'type = "pod" AND label in ("cluster-name:{COMPONENT_NAME}")'
  viewTypeIdentifier: "urn:stackpack:k8s-common-v2:shared:view-type:pod"
```

#### Complex filtering with multiple types

```yaml
- _type: "ComponentTypeRelatedResources"
  resourceType: "queue"
  title: "Queues"
  stql: |
    (
        withNeighborsOf(direction = "both", components = (
            withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "2")
            AND type IN ("process")
        ), levels = "1")
        AND type IN ("AMQP queue", "AMQP exchange")
    )
```

### Multiple Related Resources

You can define multiple related resource sections:

```yaml
relatedResources:
  - _type: "ComponentTypeRelatedResources"
    resourceType: "service instance"
    title: "Instances of this service"
    stql: '(withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1")) and type = "otel service instance"'
    viewTypeIdentifier: "urn:stackpack:open-telemetry:shared:view-type:service-instance"

  - _type: "ComponentTypeRelatedResources"
    resourceType: "service"
    title: "Related services"
    stql: '(withNeighborsOf(direction = "up", components = (withNeighborsOf(direction = "both", components = (withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1") and type = "otel service instance"), levels = "1") and type = "otel service instance") , levels = "1") and type = "otel service"'
    viewTypeIdentifier: "urn:stackpack:open-telemetry:shared:view-type:service"
```

---

## Metrics Integration

Define metric categories and bindings for the component type.

### Structure

```yaml
metrics:
  - _type: "ComponentTypeMetricCategory"
    name: "Resource usage"
    description: "CPU and memory usage"
    bindings: [
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-cpu-usage",
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-memory-usage"
    ]
    defaultExpanded: true  # Optional, defaults to true
```

### Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | String | Yes | Category name displayed in UI |
| `description` | String | Yes | Category description |
| `bindings` | Array[URN] | Yes | Array of MetricBinding identifiers |
| `defaultExpanded` | Boolean | No | Whether category is expanded by default (default: true) |

### Empty Metrics

If no metrics are available:

```yaml
metrics: []
```

### Single Category

```yaml
metrics:
  - _type: "ComponentTypeMetricCategory"
    name: "Traces"
    description: "Rate, Errors and Duration metrics for the trace spans"
    bindings: [
      "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-rate",
      "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-error-rate",
      "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-duration"
    ]
```

### Multiple Categories

```yaml
metrics:
  - _type: "ComponentTypeMetricCategory"
    name: "Resource usage"
    description: "CPU and memory usage"
    bindings: [
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-cpu-usage",
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-cpu-throttling",
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-memory-usage"
    ]

  - _type: "ComponentTypeMetricCategory"
    name: "HTTP"
    description: "HTTP response latency, throughput and statuses"
    bindings: [
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-http-response-status-percentage",
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-http-throughput",
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-http-latency"
    ]

  - _type: "ComponentTypeMetricCategory"
    name: "HTTP per upstream pod"
    description: "HTTP response latency for upstream pods"
    bindings: [
      "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-http-latency-upstream"
    ]
    defaultExpanded: false  # Collapsed by default
```

### MetricBinding Reference

Metric bindings are defined separately (usually in `metric-bindings/*.sty` files) and referenced by their URN identifier.

**Example MetricBinding definition:**
```yaml
- _type: MetricBinding
  chartType: line
  enabled: true
  unit: percentunit
  description: The percentage of errors per second
  name: Span error rate
  identifier: urn:stackpack:open-telemetry:shared:metric-binding:service-spans-error-rate
  queries:
    - expression: |
        ((sum(rate(otel_span_calls_total{status_code="STATUS_CODE_ERROR", service_namespace="${tags.service.namespace}", service_name="${name}"}[5m])) by (span_kind)) or 0)
        / sum(rate(otel_span_calls_total{service_namespace="${tags.service.namespace}", service_name="${name}"}[5m])) by (span_kind)
      alias: '${span_kind}'
  scope: (label = "stackpack:open-telemetry" and type = "otel service")
  layout:
    metricPerspective:
      tab: Traces Performance
      section: Spans
```

---

## Traces Integration

Define trace bindings to show traces for components.

### TraceBinding

Associates components with traces based on span attributes.

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

**Properties:**
- `name`: Human-readable name
- `identifier`: Unique URN identifier
- `filter`: Attribute filters to match traces
  - `attributes`: Map of span attribute filters
- `scope`: STQL query defining which components this applies to

### SpanToComponentBinding

Links spans to components in span detail views.

```yaml
- _type: SpanToComponentBinding
  name: Open-telemetry span binding to Open-telemetry service
  identifier: urn:stackpack:open-telemetry:shared:span-to-component-binding:service
  urnTemplate: "urn:opentelemetry:namespace/${resource.service.namespace}:service/${resource.service.name}"
```

**Properties:**
- `name`: Human-readable name
- `identifier`: Unique URN identifier
- `urnTemplate`: Template to generate component URN from span attributes

### Examples

#### Service-level traces

```yaml
- _type: TraceBinding
  name: Traces for Open-telemetry services
  identifier: urn:stackpack:open-telemetry:shared:trace-binding:service
  filter:
    attributes:
      service.namespace: ["${tags.service.namespace}"]
      service.name: ["${name}"]
  scope: (label = "stackpack:open-telemetry" and type = "otel service")

- _type: SpanToComponentBinding
  name: Open-telemetry span binding to Open-telemetry service
  identifier: urn:stackpack:open-telemetry:shared:span-to-component-binding:service
  urnTemplate: "urn:opentelemetry:namespace/${resource.service.namespace}:service/${resource.service.name}"
```

#### Service instance traces

```yaml
- _type: TraceBinding
  name: Traces for Open-telemetry service instances
  identifier: urn:stackpack:open-telemetry:shared:trace-binding:service-instance
  filter:
    attributes:
      service.instance.id: ["${tags.service.instance.id}"]
      service.namespace: ["${tags.service.namespace}"]
      service.name: ["${tags.service.name}"]
  scope: (label = "stackpack:open-telemetry" and type = "otel service instance")

- _type: SpanToComponentBinding
  name: Open-telemetry span binding to Open-telemetry service instance
  identifier: urn:stackpack:open-telemetry:shared:span-to-component-binding:service-instance
  urnTemplate: "urn:opentelemetry:namespace/${resource.service.namespace}:service/${resource.service.name}:serviceInstance/${resource.service.instance.id}"
```

---

## Variable Interpolation Reference

Different contexts use **different interpolation syntaxes**. Using the wrong syntax in the wrong context will silently fail.

### STQL Placeholders (relatedResources, relatedResourcesTemplate)

Used in `relatedResources` STQL queries and `relatedResourcesTemplate`. Single curly braces, no dollar sign.

| Placeholder | Description | Example |
|---|---|---|
| `{COMPONENT_ID}` | Internal component ID | `id = "{COMPONENT_ID}"` |
| `{COMPONENT_NAME}` | Component display name | `label = "service.name:{COMPONENT_NAME}"` |
| `{COMPONENT_PREDICATE}` | Component predicate expression | `withNeighborsOf(components = ({COMPONENT_PREDICATE}))` |
| `{CLUSTER_NAME}` | Cluster name (K8s) | `label = "cluster-name:{CLUSTER_NAME}"` |

**Usage patterns:**

```yaml
# Direct neighbor traversal
stql: '(withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1")) and type = "pod"'

# Label-based matching with dynamic component name
stql: 'type = "otel service instance" and label = "service.name:{COMPONENT_NAME}"'

# Combined: find services via neighbors of matched instances
stql: 'withNeighborsOf(direction = "up", components = (type = "otel service instance" and label = "service.name:{COMPONENT_NAME}"), levels = "1") and type = "otel service"'
```

### PromQL Variables (MetricBinding queries)

Used in MetricBinding `expression` fields. Dollar sign with curly braces.

| Variable | Description | Example |
|---|---|---|
| `${name}` | Component display name | `metric{service_name="${name}"}` |
| `${tags.<tag_name>}` | Component tag value | `metric{namespace="${tags.service.namespace}"}` |
| `${__rate_interval}` | Auto-calculated rate interval | `rate(metric[${__rate_interval}])` |
| `${label_name}` | PromQL label for `by()` legends | `alias: '${model_name}'` |

### TraceBinding Filter Variables

Used in TraceBinding `filter.attributes`. Dollar sign with curly braces.

| Variable | Description | Example |
|---|---|---|
| `${name}` | Component display name | `service.name: ["${name}"]` |
| `${tags.<tag_name>}` | Component tag value | `service.namespace: ["${tags.service.namespace}"]` |

### SpanToComponentBinding Variables

Used in `urnTemplate`. Dollar sign with curly braces, prefixed with `resource.` to reference span resource attributes.

| Variable | Description | Example |
|---|---|---|
| `${resource.<attr>}` | Span resource attribute | `${resource.service.name}` |

### Summary Table

| Context | Syntax | Examples |
|---|---|---|
| `relatedResources` STQL | `{PLACEHOLDER}` | `{COMPONENT_ID}`, `{COMPONENT_NAME}` |
| `relatedResourcesTemplate` | `{PLACEHOLDER}` | `{COMPONENT_ID}`, `{COMPONENT_NAME}` |
| MetricBinding queries | `${variable}` | `${name}`, `${tags.X}`, `${__rate_interval}` |
| TraceBinding filters | `${variable}` | `${name}`, `${tags.X}` |
| SpanToComponentBinding | `${resource.X}` | `${resource.service.name}` |
| Monitor urnTemplate | `${label}` | `${service_name}`, `${suse_ai_component_name}` |

**Key rule:** STQL uses `{SINGLE_BRACES}`. Everything else uses `${DOLLAR_BRACES}`.

---

## Best Practices

### 1. Identifier Naming

**Use consistent URN patterns:**
```yaml
# Good
identifier: "urn:stackpack:kubernetes-v2:shared:component-type:pod"
identifier: "urn:stackpack:open-telemetry:shared:component-type:service"

# Avoid
identifier: "my-pod-type"
identifier: "service"
```

### 2. Icon Management

**Store icons in a dedicated directory:**
```
provisioning/
  icons/
    service.png
    database.png
    pod.png
  component-types/
    services.sty
```

**Use Handlebars include:**
```yaml
iconbase64: "{{ include "./icons/service.png" "base64" }}"
```

### 3. Field Organization

**Standard field order:**
1. `type` (always first)
2. `health` (always second)
3. Status/state fields (readyContainers, phase, etc.)
4. Metadata fields (age, ip, etc.)
5. Links to related components (namespace, cluster, owner, etc.)
6. `labels` (usually last)

**Example:**
```yaml
fields:
  - type
  - health
  - readyContainers
  - phase
  - restarts
  - age
  - ip
  - node
  - owner
  - namespace
  - cluster
  - labels
```

### 4. About Section

**Keep it concise:**
```yaml
# Good: 7 fields
about:
  _type: "ComponentTypeAbout"
  fields: ["type", "health", "age", "serviceType", "clusterIP", "namespace", "labels"]

# Too many: 15+ fields makes it hard to scan
about:
  _type: "ComponentTypeAbout"
  fields: ["type", "health", "field1", "field2", "field3", ...] # 15+ fields
```

### 5. Related Resources

**Order by relevance:**
1. Direct children/parents
2. Peers
3. Indirect relationships

**Example for Kubernetes Service:**
```yaml
relatedResources:
  # Direct children first
  - title: "Pods of this service"
    stql: '...'

  # Related peers
  - title: "Related services"
    stql: '...'

  # Indirect relationships
  - title: "Queues"
    stql: '...'
```

### 6. Metrics Organization

**Group related metrics:**
```yaml
metrics:
  # Core performance metrics
  - name: "Resource usage"
    bindings: ["cpu", "memory"]

  # Application metrics
  - name: "HTTP"
    bindings: ["latency", "throughput", "errors"]

  # Detailed metrics (collapsed by default)
  - name: "HTTP per downstream"
    bindings: ["latency-downstream"]
    defaultExpanded: false
```

### 7. STQL Query Performance

**Use specific queries:**
```yaml
# Good: Specific type and level
stql: '(withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1")) and type = "pod"'

# Avoid: Too broad
stql: '(withNeighborsOf(direction = "both", components = (id = "{COMPONENT_ID}"), levels = "10"))'
```

### 8. External ID Selectors

**Use precise patterns:**
```yaml
# Good: Precise regex
externalIdSelector: "^urn:kubernetes:"

# Avoid: Too broad
externalIdSelector: ".*"

# Good: Empty for no external integration
externalIdSelector: ""
```

### 9. Logs and Events

**Enable logs only for components that generate them:**
```yaml
# Pods generate logs
showLogs: true

# Services don't have direct logs
showLogs: false
```

**Use meaningful event queries:**
```yaml
# Good: Include related resources
relatedResourcesTemplate: |
  (withNeighborsOf(direction = "up", components = (id = "{COMPONENT_ID}"), levels = "2")
   AND type IN ("deployment", "replicaset"))
  OR id = "{COMPONENT_ID}"

# Avoid: No context
relatedResourcesTemplate: 'id = "{COMPONENT_ID}"'
```

### 10. Documentation

**Add descriptions for complex component types:**
```yaml
- _type: "ComponentType"
  name: "otel service"
  description: "OpenTelemetry service representing a logical service aggregating multiple service instances"
  # ...
```

**Use help bubbles for non-obvious fields:**
```yaml
- _type: "ComponentTypeField"
  fieldId: "age"
  label:
    title: "Age"
    helpBubbleText: "This is the creation time relative to the current time of the view"
  # ...
```

---

## Complete Examples

### Example 1: Kubernetes Pod (Full-Featured)

```yaml
- _type: "ComponentType"
  iconbase64: "{{ include "./icons/pod.png" "base64" }}"
  identifier: "urn:stackpack:kubernetes-v2:shared:component-type:pod"
  name: "pod"
  highlights:
    _type: "ComponentTypeExt"
    namePlural: "pods"
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

      - _type: "ComponentTypeField"
        fieldId: "readyContainers"
        label:
          title: "Ready containers"
        valueExtractor:
          _type: "CompositeSource"
          sources:
            status:
              _type: "PropertySource"
              key: "readyContainersStatus"
            ready:
              _type: "PropertySource"
              key: "readyContainers"
            total:
              _type: "PropertySource"
              key: "totalContainers"
        display:
          _type: "ReadyStatusDisplay"

      - _type: "ComponentTypeField"
        fieldId: "phase"
        label:
          title: "Phase"
        valueExtractor:
          _type: "PropertySource"
          key: "podPhase"
          defaultValue: "UNKNOWN"
        display:
          _type: "TextDisplay"

      - _type: "ComponentTypeField"
        fieldId: "age"
        label:
          title: "Age"
          helpBubbleText: "This is the creation time relative to the current time of the view"
        valueExtractor:
          _type: "PropertySource"
          key: "creationTimestamp"
        display:
          _type: "DurationDisplay"

      - _type: "ComponentTypeField"
        fieldId: "namespace"
        label:
          title: "Namespace"
        valueExtractor:
          _type: "CompositeSource"
          sources:
            name:
              _type: "TagSource"
              tagName: "namespace"
            identifier:
              _type: "PropertySource"
              key: "namespaceIdentifier"
        display:
          _type: "ComponentLinkDisplay"

      - _type: "ComponentTypeField"
        fieldId: "labels"
        label:
          title: "Labels"
        valueExtractor:
          _type: "TagsSource"
        display:
          _type: "TagDisplay"
          singular: "label"

    about:
      _type: "ComponentTypeAbout"
      fields: ["type", "health", "readyContainers", "phase", "age", "namespace", "labels"]

    events:
      _type: "ComponentTypeEvents"
      showEvents: true
      relatedResourcesTemplate: |
        (withNeighborsOf(direction = "both", components = ({COMPONENT_PREDICATE}), levels = "2")
         AND type IN ("deployment", "statefulset", "daemonset"))
        OR ({COMPONENT_PREDICATE})

    showLogs: true
    showLastChange: true

    externalComponent:
      _type: "ComponentTypeExternalComponent"
      showConfiguration: true
      showStatus: true
      externalIdSelector: "^urn:kubernetes:"

    relatedResources:
      - _type: "ComponentTypeRelatedResources"
        resourceType: "service"
        title: "Related services"
        stql: '(withNeighborsOf(direction = "both", components = (id = "{COMPONENT_ID}"), levels = "1")) and type = "service"'
        viewTypeIdentifier: "urn:stackpack:k8s-common-v2:shared:view-type:service"

      - _type: "ComponentTypeRelatedResources"
        resourceType: "container"
        title: "Containers"
        stql: '(withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1")) and type = "container"'

    metrics:
      - _type: "ComponentTypeMetricCategory"
        name: "Resource usage"
        description: "CPU and memory usage"
        bindings: [
          "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-cpu-usage",
          "urn:stackpack:kubernetes-v2:shared:metric-binding:pod-memory-usage"
        ]
```

### Example 2: OpenTelemetry Service (With Traces)

```yaml
- _type: "ComponentType"
  iconbase64: "{{ include "./icons/service.png" "base64" }}"
  identifier: "urn:stackpack:open-telemetry:shared:component-type:service"
  name: "otel service"
  highlights:
    _type: "ComponentTypeHighlight"
    namePlural: "services"
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

      - _type: "ComponentTypeField"
        fieldId: "namespace"
        label:
          title: "Otel Namespace"
        valueExtractor:
          _type: "CompositeSource"
          sources:
            name:
              _type: "TagSource"
              tagName: "service.namespace"
            identifier:
              _type: "PropertySource"
              key: "namespaceIdentifier"
        display:
          _type: "ComponentLinkDisplay"

      - _type: "ComponentTypeField"
        fieldId: "labels"
        label:
          title: "Labels"
        valueExtractor:
          _type: "TagsSource"
        display:
          _type: "TagDisplay"
          singular: "label"

    about:
      _type: "ComponentTypeAbout"
      fields: ["type", "health", "namespace", "labels"]

    events:
      _type: "ComponentTypeEvents"
      showEvents: true
      relatedResourcesTemplate: |
        (withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1")
         and type = "otel service instance")
        OR id = "{COMPONENT_ID}"

    showLogs: false
    showLastChange: false

    externalComponent:
      _type: "ComponentTypeExternalComponent"
      showConfiguration: false
      showStatus: false
      externalIdSelector: "^urn:open-telemetry:"

    relatedResources:
      - _type: "ComponentTypeRelatedResources"
        resourceType: "service instance"
        title: "Instances of this service"
        stql: '(withNeighborsOf(direction = "down", components = (id = "{COMPONENT_ID}"), levels = "1")) and type = "otel service instance"'
        viewTypeIdentifier: "urn:stackpack:open-telemetry:shared:view-type:service-instance"

    metrics:
      - _type: "ComponentTypeMetricCategory"
        name: "Traces"
        description: "Rate, Errors and Duration metrics for the trace spans"
        bindings: [
          "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-rate",
          "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-error-rate",
          "urn:stackpack:open-telemetry:shared:metric-binding:service-spans-duration"
        ]

# Associated trace bindings
- _type: TraceBinding
  name: Traces for Open-telemetry services
  identifier: urn:stackpack:open-telemetry:shared:trace-binding:service
  filter:
    attributes:
      service.namespace: ["${tags.service.namespace}"]
      service.name: ["${name}"]
  scope: (label = "stackpack:open-telemetry" and type = "otel service")

- _type: SpanToComponentBinding
  name: Open-telemetry span binding to Open-telemetry service
  identifier: urn:stackpack:open-telemetry:shared:span-to-component-binding:service
  urnTemplate: "urn:opentelemetry:namespace/${resource.service.namespace}:service/${resource.service.name}"
```

### Example 3: Minimal Component Type

```yaml
- _type: ComponentType
  iconbase64: "{{ include "./icons/database.png" "base64" }}"
  identifier: "urn:stackpack:common:component-type:database"
  name: "database"
```

### Example 4: Simple Component Type with Basic Highlights

```yaml
- _type: ComponentType
  iconbase64: "{{ include "./icons/host.png" "base64" }}"
  identifier: "urn:stackpack:stackstate-k8s-agent-v2:shared:component-type:host"
  name: "host"
  ownedBy: "urn:stackpack:stackstate-k8s-agent-v2"
```

---

## Summary

ComponentType definitions are the foundation of how components appear and behave in StackState. Key takeaways:

1. **Always include** `type` and `health` fields
2. **Use CompositeSource with ComponentLinkDisplay** for component links
3. **Organize metrics** into logical categories
4. **Write specific STQL queries** for related resources
5. **Enable logs and events** only when appropriate
6. **Use consistent URN naming** conventions
7. **Add help text** for complex fields
8. **Group related resources** logically
9. **Test your queries** before deploying
10. **Document complex configurations** with comments

This guide covers all aspects of ComponentType definitions based on real-world examples from the StackState StackPacks repository. Use it as a reference when creating or modifying component types in your StackPacks.
