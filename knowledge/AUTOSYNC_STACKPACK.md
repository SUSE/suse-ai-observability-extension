# Autosync StackPack Analysis

Reference: extracted from `autosync-3.2.1-stac-0-bump-1037-203fef5-SNAPSHOT.sts`

## Overview

The "Custom Synchronization" StackPack provides a generic passthrough for topology data. It creates a separate sync that reads from a custom Kafka topic and creates components/relations directly from the data payload, with whatever type/layer/domain the data specifies.

## Architecture

```
Custom Agent / Data Source
    |
    | Topology API → Kafka topic (type + url)
    v
Autosync StackPack Instance
    - Component ID extractor (passthrough)
    - Relation ID extractor (passthrough)
    - Component template (resolveOrCreate for types/layers)
    - Relation template (resolveOrCreate for relation types)
    |
    v
SUSE Observability Topology
```

## Key Components

### Component ID Extractor
```groovy
element = topologyElement.asReadonlyMap()
externalId = element["externalId"]
type = element["typeName"].toLowerCase()
data = element["data"]
identifiers = new HashSet()
if(data.containsKey("identifiers") && data["identifiers"] instanceof List<String>) {
    data["identifiers"].each{ id -> identifiers.add(id) }
}
return Sts.createId(externalId, identifiers, type)
```
- Uses `externalId` as-is
- Reads `data.identifiers` (a list) from the payload and passes them as identifiers
- Type comes from `element.typeName` (lowercased)

### Relation ID Extractor
```groovy
element = topologyElement.asReadonlyMap()
externalId = element["externalId"]
type = element["typeName"].toLowerCase()
return Sts.createId(externalId, new HashSet(), type)
```
- Simple passthrough, no identifiers

### Component Template
- Uses `resolveOrCreate` for ComponentType, Layer, Domain, Environment — auto-creates if missing
- Labels include integration metadata (`integrationType:integrationUrl`) plus `data.labels` and `data.tags`
- Name from `data.name`, fallback to `externalId`

### Relation Template
- Source/target from `element.sourceId` / `element.targetId` (pre-resolved internal IDs)
- Type via `resolveOrCreate` for RelationType
- Default `dependencyDirection: ONE_WAY`

### Sync Configuration
- `MergePreferTheirs` for both components and relations
- Reads from a Kafka topic derived from `sts_instance_type` + `sts_instance_url`

## Key Patterns

### `data.identifiers` Pattern
Topology elements can carry pre-defined identifiers in their data payload. The ID extractor reads and passes them through. This allows the data source to control cross-sync merging.

### `resolveOrCreate` Pattern
Templates auto-create ComponentTypes, Layers, Domains, Environments on-the-fly if they don't exist. Useful for generic/dynamic topology.

### Separate Kafka Topic
Each autosync instance reads from its own Kafka topic, keeping topology data isolated from other syncs.

## Relevance to SUSE AI Product Relations

### Why Autosync Doesn't Solve Product-to-Product Relations

The goal was to create topology arrows between product components (e.g., inference-engine → llm-model). Analysis:

1. **Relation source/target resolved by externalId only** — identifiers don't help with relation resolution
2. **Product components have `suse-ai:product:*` externalIds** — OTel relations reference OTel URNs, not product externalIds
3. **Adding unprefixed OTel URN as identifier** — causes product components to merge with OTel service components, making them look like OTel services (breaks type/monitors)
4. **Autosync requires a separate data source** — something must produce topology data to a Kafka topic with product externalIds as source/target, adding infrastructure complexity
5. **OTel collector exports via OTLP** — can't inject arbitrary topology relations through the OTLP protocol

### Options Explored

| Approach | Result |
|----------|--------|
| Identifier-based merge (unprefixed OTel URN) | Breaks product types, makes everything look like OTel services |
| Scoped merge (inference engines only) | Same issue for affected components |
| Autosync custom topology source | Requires custom data producer + Kafka topic — too heavy |
| Accept no arrows on products | Use related resources tab for navigation instead |

### Current Decision
Product components do NOT merge with OTel services. Instead, a custom OTel exporter (`topologyexporter`) in the `otelcol-suse-ai` collector discovers topology from GenAI/DB spans and pushes explicit components + relations (using product externalIds) to the receiver API. A dedicated "SUSE AI Topology" sync in the StackPack consumes this data with `MergePreferTheirs`, so the product sync's richer metadata wins. This gives topology arrows between product components without breaking types or monitors.
