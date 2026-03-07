# StackPacks Kafka Topics Report

## Executive Summary

This report provides a comprehensive analysis of Kafka topics used by StackState StackPacks. Out of 16 analyzed StackPacks, 10 consume data from Kafka topics for topology synchronization. These topics follow a consistent naming convention and contain topology data (components and relations) in StackState's proprietary format.

---

## Table of Contents

1. [Kafka Topics Overview](#kafka-topics-overview)
2. [Topic Naming Convention](#topic-naming-convention)
3. [StackPacks Using Kafka Topics](#stackpacks-using-kafka-topics)
4. [Topic Details by StackPack](#topic-details-by-stackpack)
5. [Data Format and Structure](#data-format-and-structure)
6. [How to Consume Kafka Topics](#how-to-consume-kafka-topics)
7. [StackPacks NOT Using Kafka Topics](#stackpacks-not-using-kafka-topics)

---

## Kafka Topics Overview

All topology-related Kafka topics in StackState follow a consistent pattern:

```
sts-topo-<integration-type>-<instance-identifier>
```

These topics are created using the StackState provisioning API method:
```groovy
context().sts().createTopologyTopicName(prefix, identifier)
```

### Common Characteristics

- **Data Type**: TOPOLOGY_ELEMENTS
- **Format**: StackState Topology Sync format (JSON/YAML)
- **Content**: Components (nodes) and Relations (edges) representing infrastructure topology
- **Auto-Expire**: Configurable per datasource (varies by integration)
- **Processing**: Consumed via TopologySyncStream with batch processing support

---

## Topic Naming Convention

The topic name is constructed as follows:

1. **Prefix**: `sts-topo-` (topology data)
2. **Integration Type**: The source system type (e.g., `kubernetes`, `dynatrace`, `zabbix`)
3. **Instance Identifier**: Unique identifier for the specific instance (sanitized)

**Sanitization Rules**:
- Forward slashes (`/`) are replaced with underscores (`_`)
- Colons (`:`) are replaced with underscores (`_`)
- This ensures Kafka topic name compatibility

---

## StackPacks Using Kafka Topics

| StackPack | Topic Prefix | Instance Identifier | Example Topic Name |
|-----------|--------------|---------------------|-------------------|
| Zabbix | `Zabbix` | Sanitized instance URL | `sts-topo-Zabbix-10_0_0_1_zabbix` |
| Static Topology | `StaticTopology` | Sanitized CSV path | `sts-topo-StaticTopology-_data_components_csv` |
| VSphere | `vsphere` | Host name | `sts-topo-vsphere-vcenter.example.com` |
| Kubernetes | `kubernetes` | Cluster name | `sts-topo-kubernetes-production-cluster` |
| Kubernetes V2 | `kubernetes` | Cluster name | `sts-topo-kubernetes-prod-k8s-01` |
| Dynatrace | `dynatrace` | Host URL | `sts-topo-dynatrace-abc12345.live.dynatrace.com` |
| Dynatrace V2 | `dynatrace` | Host URL | `sts-topo-dynatrace-abc12345.live.dynatrace.com` |
| ServiceNow | `servicenow` | `cmdb_<instance_url>` | `sts-topo-servicenow-cmdb_dev12345` |
| StackState Agent V2 | `process` | `agents` | `sts-topo-process-agents` |
| StackState K8s Agent V2 | `process` | `agents` | `sts-topo-process-agents` |

---

## Topic Details by StackPack

### 1. Zabbix

**Topic Pattern**: `sts-topo-Zabbix-<sanitized_instance_url>`

**Data Description**:
- Zabbix monitoring infrastructure topology
- Components: Hosts, host groups, applications, items, triggers
- Relations: Host-to-hostgroup, application-to-host, item-to-application relationships
- Metrics: Trigger states, item values

**Configuration Source**:
```groovy
File: zabbix/src/main/stackpack/provisioning/ZabbixProvision.groovy
Topic Creation: Line 43
```

**Instance URL Processing**:
- Extracts domain from full URL (removes protocol and path)
- Example: `https://10.0.0.1/zabbix/api` → `10.0.0.1`

**Auto-Expire**: Disabled (elements persist until explicitly removed)

**Typical Data Source**: Zabbix Agent check running on SUSE Observability Agent V2

---

### 2. Static Topology

**Topic Pattern**: `sts-topo-StaticTopology-<sanitized_csv_path>`

**Data Description**:
- Custom topology from CSV files
- Components: Defined in component CSV file
- Relations: Defined in relation CSV file
- Use case: Manual topology definition or integration with custom CMDB systems

**Configuration Source**:
```groovy
File: static-topology/src/main/stackpack/provisioning/StaticTopologyProvision.groovy
Topic Creation: Line 39
```

**CSV Path Processing**:
- Uses component CSV path as identifier
- Example: `/data/components.csv` → `_data_components.csv`

**Auto-Expire**: Disabled

**Typical Data Source**: Static Topology Agent check or custom data pusher

---

### 3. VSphere

**Topic Pattern**: `sts-topo-vsphere-<host_name>`

**Data Description**:
- VMware vSphere infrastructure topology
- Components: vCenters, ESXi hosts, clusters, resource pools, VMs, datastores, networks
- Relations: VM-to-host, host-to-cluster, datastore connections
- Metrics: Resource utilization, performance counters

**Configuration Source**:
```groovy
File: vsphere/src/main/stackpack/provisioning/VSphereProvision.groovy
Topic Creation: Line 40
```

**Identifier**: Direct hostname (no sanitization applied)

**Auto-Expire**: Disabled

**Typical Data Source**: VSphere Agent check

---

### 4. Kubernetes / Kubernetes V2

**Topic Pattern**: `sts-topo-kubernetes-<cluster_name>`

**Data Description**:
- Kubernetes cluster topology
- Components: Namespaces, pods, containers, services, deployments, replica sets, daemon sets, stateful sets, nodes, persistent volumes, config maps, secrets
- Relations: Pod-to-node, container-to-pod, service-to-pod, deployment-to-replicaset relationships
- Metrics: Container metrics, pod metrics, node metrics
- Events: Kubernetes events

**Configuration Source**:
```groovy
# Kubernetes
File: kubernetes/src/main/stackpack/provisioning/KubernetesProvision.groovy
Topic Creation: Line 46

# Kubernetes V2
File: kubernetes-v2/src/main/stackpack/provisioning/KubernetesV2Provision.groovy
Topic Creation: Line 46
```

**Cluster Name Validation**:
- **Kubernetes**: `^[\w_]([\w_.-]*[\w_])?$` (letters, numbers, `_`, `.`, `-`)
- **Kubernetes V2**: `^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])$` (lowercase only, stricter)

**Auto-Expire**: Enabled (10800000ms = 3 hours)

**Typical Data Source**:
- Kubernetes: StackState Agent V2 with Kubernetes integration
- Kubernetes V2: StackState K8s Agent V2

---

### 5. Dynatrace / Dynatrace V2

**Topic Pattern**: `sts-topo-dynatrace-<host_url>`

**Data Description**:
- Dynatrace monitored environment topology
- Components: Hosts, processes, services, applications, synthetic monitors
- Relations: Process-to-host, service-to-process, application-to-service relationships
- Metrics: Dynatrace metrics and problems

**Configuration Source**:
```groovy
# Dynatrace
File: dynatrace/src/main/stackpack/provisioning/DynatraceProvision.groovy
Topic Creation: Line 41

# Dynatrace V2
File: dynatrace-v2/src/main/stackpack/provisioning/DynatraceProvision.groovy
Topic Creation: Line 41
```

**Identifier**: Full Dynatrace tenant URL
- Example: `abc12345.live.dynatrace.com`

**Auto-Expire**: Disabled

**Typical Data Source**: Dynatrace Agent check

---

### 6. ServiceNow

**Topic Pattern**: `sts-topo-servicenow-cmdb_<instance_url>`

**Data Description**:
- ServiceNow CMDB topology
- Components: Configuration Items (CIs) from ServiceNow CMDB (servers, applications, databases, network devices)
- Relations: CI relationships as defined in ServiceNow
- Use case: CMDB synchronization and correlation with runtime data

**Configuration Source**:
```groovy
File: servicenow/src/main/stackpack/provisioning/ServiceNowProvision.groovy
Topic Creation: Line 39
```

**Identifier**: `cmdb_<instance_url>` prefix
- Example instance URL: `dev12345` → Topic: `sts-topo-servicenow-cmdb_dev12345`

**Auto-Expire**: Disabled

**Typical Data Source**: ServiceNow Agent check

---

### 7. StackState Agent V2 / StackState K8s Agent V2

**Topic Pattern**: `sts-topo-process-agents`

**Data Description**:
- Agent-discovered process and container topology
- Components: Hosts, processes, containers, network connections
- Relations: Process-to-host, container-to-host, network connections between processes
- Metrics: Process metrics, container metrics, system metrics

**Configuration Source**:
```groovy
# StackState Agent V2
File: stackstate-agent-v2/src/main/stackpack/provisioning/StackStateAgentV2Provision.groovy
Topic Creation: Line 38

# StackState K8s Agent V2
File: stackstate-k8s-agent-v2/src/main/stackpack/provisioning/StackStateK8sAgentV2Provision.groovy
Topic Creation: Line 38
```

**Identifier**: Fixed value `agents` (shared topic for all agent instances)

**Auto-Expire**: Configuration varies

**Typical Data Source**: StackState Agent V2 process agent

**Note**: Both agent StackPacks use the same topic, consolidating all agent data into a single stream.

---

## Data Format and Structure

### Topology Data Format

All topics contain data in StackState's Topology Sync format, which includes:

#### Data Source Configuration
```json
{
  "_type": "DataSource",
  "config": {
    "_type": "Sts.StsTopologyDataSourceConfig",
    "autoExpireElements": false,
    "expireElementsAfter": 172800000,
    "integrationType": "integration-name",
    "supportedDataTypes": ["TOPOLOGY_ELEMENTS"],
    "topic": "topic-name"
  }
}
```

#### Topology Query Configuration
```json
{
  "_type": "Sts.StsTopologyElementsQuery",
  "componentIdExtractorFunction": "function-id",
  "relationIdExtractorFunction": "function-id",
  "consumerOffsetStartAtEarliest": false
}
```

#### Sync Configuration
```json
{
  "_type": "TopologySyncSettings",
  "cleanupExpiredElements": false,
  "cleanupInterval": 3600000,
  "maxBatchSize": 200,
  "maxBatchesPerSecond": 5
}
```

### Message Structure

Each message in the topic contains topology elements in JSON format:

**Components** (Nodes):
```json
{
  "externalId": "unique-component-id",
  "type": "component-type",
  "data": {
    "name": "component-name",
    "labels": ["label1", "label2"],
    "identifiers": ["identifier1"],
    "layer": "layer-name",
    "domain": "domain-name",
    "environment": "environment-name"
  }
}
```

**Relations** (Edges):
```json
{
  "externalId": "unique-relation-id",
  "type": "relation-type",
  "sourceId": "source-component-id",
  "targetId": "target-component-id",
  "data": {
    "labels": ["label1"]
  }
}
```

---

## How to Consume Kafka Topics

### Using StackPack Provisioning API (Groovy)

The standard pattern used by all StackPacks:

#### 1. Create Topic Name

```groovy
private def topicName(Map<String, Object> config) {
  def identifier = config.instance_identifier
  // Apply sanitization if needed
  def sanitized = identifier.replace("/", "_").replace(":", "_")
  return context().sts().createTopologyTopicName("integration-type", sanitized)
}
```

#### 2. Register Data Listener

```groovy
@Override
void waitingForData(Map<String, Object> config) {
  context().sts().onDataReceived(topicName(config), {
    context().sts().provisioningComplete()
  })
}
```

#### 3. Configure Data Source

In template files (`.stj` or `.sty`):

```yaml
nodes:
  - _type: DataSource
    name: "Integration Name"
    identifier: "urn:stackpack:integration:instance:{{instanceId}}:data-source:name"
    pluginId: Sts
    config:
      _type: Sts.StsTopologyDataSourceConfig
      topic: '{{ topicName }}'
      integrationType: integration-name
      supportedDataTypes:
        - TOPOLOGY_ELEMENTS
      autoExpireElements: true
      expireElementsAfter: 10800000
```

### Direct Kafka Consumption (External)

For external systems consuming these topics directly:

#### Connection Parameters

```properties
# Standard Kafka connection
bootstrap.servers=kafka-broker:9092
group.id=custom-consumer-group
auto.offset.reset=latest
enable.auto.commit=false
```

#### Consumer Pattern

```java
// Java example
Properties props = new Properties();
props.put("bootstrap.servers", "kafka-broker:9092");
props.put("group.id", "topology-consumer");
props.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
props.put("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");

KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props);
consumer.subscribe(Arrays.asList("sts-topo-kubernetes-production"));

while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, String> record : records) {
        // Parse JSON topology data
        processTopologyData(record.value());
    }
}
```

#### Python Example

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'sts-topo-kubernetes-production',
    bootstrap_servers=['kafka-broker:9092'],
    group_id='topology-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for message in consumer:
    topology_data = message.value
    # Process components and relations
    process_topology(topology_data)
```

### Multi-Topic Consumption

To consume data from multiple integrations:

```groovy
// Subscribe to multiple topics
def topics = [
  topicName("kubernetes", "prod-cluster"),
  topicName("dynatrace", "tenant-id"),
  topicName("servicenow", "cmdb_prod")
]

topics.each { topic ->
  context().sts().onDataReceived(topic, { data ->
    // Process data from any source
    processTopologyData(data)
  })
}
```

### Synchronization Settings

Key parameters for consuming topology data:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `maxBatchSize` | 200 | Maximum number of elements per batch |
| `maxBatchesPerSecond` | 5 | Rate limiting for batch processing |
| `cleanupInterval` | 3600000ms | Interval for cleanup operations (1 hour) |
| `autoExpireElements` | Varies | Whether to auto-expire stale elements |
| `expireElementsAfter` | Varies | Time before elements expire (if enabled) |
| `consumerOffsetStartAtEarliest` | false | Start from earliest or latest offset |

---

## StackPacks NOT Using Kafka Topics

The following StackPacks do not consume Kafka topics and use alternative integration methods:

### 1. Open Telemetry
- **Integration Method**: Direct OTLP receiver
- **Data Types**: Traces, metrics, logs
- **Schema Version**: 2.0 (declarative config, no Groovy)

### 2. Artifactory
- **Integration Method**: Not specified (likely pull-based API)
- **Schema Version**: Unknown

### 3. Community Kubernetes
- **Integration Method**: Template-based, no dynamic data ingestion
- **Schema Version**: 2.0 (declarative config)

### 4. Prime Kubernetes
- **Integration Method**: Template-based, no dynamic data ingestion
- **Schema Version**: 2.0 (declarative config)

### 5. StackState / StackState Tenants
- **Integration Method**: Internal StackState components
- **Purpose**: Core platform functionality, not external integration

### 6. AAD / AAD V2
- **Integration Method**: Not analyzed (no Groovy provision files found)
- **Purpose**: Anomaly detection and dynamic thresholds

---

## Summary Table: All Kafka Topics

| Topic Name Pattern | Integration | Data Content | Auto-Expire | Typical Use Case |
|-------------------|-------------|--------------|-------------|------------------|
| `sts-topo-Zabbix-*` | Zabbix | Monitoring infrastructure | No | Zabbix monitoring integration |
| `sts-topo-StaticTopology-*` | Static CSV | Custom topology | No | Manual topology definition |
| `sts-topo-vsphere-*` | VMware | Virtual infrastructure | No | VMware monitoring |
| `sts-topo-kubernetes-*` | Kubernetes | K8s resources | Yes (3h) | Container orchestration |
| `sts-topo-dynatrace-*` | Dynatrace | APM topology | No | Application performance monitoring |
| `sts-topo-servicenow-cmdb_*` | ServiceNow | CMDB data | No | CMDB synchronization |
| `sts-topo-process-agents` | Agent V2 | Processes & containers | Varies | Host & process monitoring |

---

## Best Practices

### For StackPack Developers

1. **Topic Naming**:
   - Use descriptive integration type prefixes
   - Sanitize identifiers to ensure Kafka compatibility
   - Keep identifiers concise but meaningful

2. **Data Expiration**:
   - Enable auto-expire for highly dynamic environments (e.g., Kubernetes)
   - Disable for stable infrastructure (e.g., CMDB data)
   - Set appropriate expiration times based on data volatility

3. **Batch Processing**:
   - Tune `maxBatchSize` based on element size and frequency
   - Adjust `maxBatchesPerSecond` to prevent overwhelming downstream systems
   - Monitor consumer lag and adjust accordingly

4. **Error Handling**:
   - Implement retry logic for transient failures
   - Use dead letter queues for permanently failed messages
   - Log processing errors for debugging

### For Data Consumers

1. **Consumer Groups**:
   - Use unique consumer group IDs for independent processing
   - Share consumer group IDs for load balancing

2. **Offset Management**:
   - Use `consumerOffsetStartAtEarliest: false` for new deployments
   - Commit offsets only after successful processing
   - Monitor consumer lag

3. **Schema Evolution**:
   - Handle schema changes gracefully
   - Use versioned data formats where possible
   - Test with sample data before deploying

---

## Appendix: File Locations

### Provisioning Scripts

```
stackpacks/
├── zabbix/src/main/stackpack/provisioning/ZabbixProvision.groovy
├── static-topology/src/main/stackpack/provisioning/StaticTopologyProvision.groovy
├── vsphere/src/main/stackpack/provisioning/VSphereProvision.groovy
├── kubernetes/src/main/stackpack/provisioning/KubernetesProvision.groovy
├── kubernetes-v2/src/main/stackpack/provisioning/KubernetesV2Provision.groovy
├── dynatrace/src/main/stackpack/provisioning/DynatraceProvision.groovy
├── dynatrace-v2/src/main/stackpack/provisioning/DynatraceProvision.groovy
├── servicenow/src/main/stackpack/provisioning/ServiceNowProvision.groovy
├── stackstate-agent-v2/src/main/stackpack/provisioning/StackStateAgentV2Provision.groovy
└── stackstate-k8s-agent-v2/src/main/stackpack/provisioning/StackStateK8sAgentV2Provision.groovy
```

### Template Files

```
stackpacks/
├── zabbix/src/main/stackpack/provisioning/templates/zabbix-instance-template.stj
├── kubernetes-v2/src/main/stackpack/provisioning/templates/kubernetes-v2-instance-template.sty
└── servicenow/src/main/stackpack/provisioning/templates/servicenow-instance-template.stj
```

---

## Conclusion

StackState utilizes Kafka topics extensively for topology data synchronization across multiple integration types. The consistent topic naming convention (`sts-topo-<type>-<identifier>`) and standardized data format enable scalable, real-time topology ingestion from diverse sources. Understanding these patterns is essential for:

- Developing new StackPack integrations
- Consuming topology data for external processing
- Troubleshooting data ingestion issues
- Monitoring and optimizing data pipelines

For additional information, refer to the individual StackPack documentation and provisioning scripts in the repository.

---

**Report Generated**: 2026-03-07
**Repository**: stackpacks/stackpacks
**Analysis Scope**: 16 StackPacks examined
