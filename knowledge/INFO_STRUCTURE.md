# Kafka Topology Data Structure

This document describes the format of the data received in the Kafka topic for topology information.

## Overview

The data is an array of Kafka message objects. Each object contains the Kafka metadata and a `message` field which holds the actual topology data.

## Top-Level Structure (Kafka Envelope)

| Field | Type | Description |
| :--- | :--- | :--- |
| `key` | String | Unique identifier for the message, often a URN or a host name. |
| `offset` | Integer | Kafka offset. |
| `partition` | Integer | Kafka partition. |
| `message` | Object | Contains the `TopologyElement`. |

## TopologyElement Structure

Located under `message.TopologyElement`.

| Field | Type | Description |
| :--- | :--- | :--- |
| `collectionHost` | String | The host that collected the data (e.g., `sts-otel-collector`, `correlator`). |
| `collectionTimestamp` | Long | Epoch timestamp (milliseconds) when the data was collected. |
| `ingestionTimestamp` | Long | Epoch timestamp (milliseconds) when the data was ingested (optional). |
| `payload` | Object | Contains either a `TopologyRelation` or a `TopologyComponent`. |

## Payload Types

The `payload` object is polymorphic and contains exactly one of the following keys:

### 1. TopologyRelation
Used to describe relationships between elements (e.g., a service providing an instance, a process running in a container, a network connection).

| Field | Type | Description |
| :--- | :--- | :--- |
| `externalId` | String | Unique URN for the relation. |
| `sourceId` | String | URN of the source element. |
| `targetId` | String | URN of the target element. |
| `typeName` | String | Type of relation (e.g., `provided-by`, `runs`, `directional_connection`). |
| `data` | String | **JSON String**. Contains additional metadata (e.g., `{"tags":{}}`, protocol info). |

### 2. TopologyComponent
Used to describe a single element in the topology (e.g., a process, a pod, a service).

| Field | Type | Description |
| :--- | :--- | :--- |
| `externalId` | String | Unique URN for the component. |
| `typeName` | String | Type of component (e.g., `process`). |
| `data` | String | **JSON String**. Contains detailed attributes (e.g., `pid`, `host`, `tags`, `command` args, `user` info). |

## Instructions for Consumers

1.  **Parsing `data`:** The `data` field inside both `TopologyRelation` and `TopologyComponent` is a stringified JSON. Consumers **must** parse this string to access internal attributes like tags, process IDs, or network protocols.
2.  **Polymorphic Payload:** Always check for the presence of `TopologyRelation` or `TopologyComponent` within the `payload` object to determine how to process the message.
3.  **URN Identification:** Use `externalId`, `sourceId`, and `targetId` to uniquely identify and link elements across different messages.
4.  **Timestamps:** Use `collectionTimestamp` for ordering events if multiple updates for the same element are received.
