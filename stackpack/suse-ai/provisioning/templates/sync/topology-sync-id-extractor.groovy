// Passthrough ID extractor for the topology sync.
// Uses externalId as-is and reads identifiers from data.identifiers.

if (topologyElement == null) {
    return null
}

element = topologyElement.asReadonlyMap()

externalId = element["externalId"]?.toString()
if (externalId == null) {
    return null
}

type = (element["typeName"] ?: "unknown").toString().toLowerCase()
data = element["data"] ?: [:]

identifiers = new HashSet()

if (data.containsKey("identifiers") && data["identifiers"] instanceof List) {
    data["identifiers"].each { id ->
        if (id != null) {
            identifiers.add(id.toString())
        }
    }
}

def componentName = data["name"]?.toString()
def registryLegacyId = "urn:suse-ai:product:inference-engine:kubeflow-model-registry".toString()
if (componentName == "kubeflow-model-registry" || externalId == registryLegacyId) {
    def normalizedId = "urn:suse-ai:product:ml-registry:kubeflow-model-registry".toString()
    identifiers.add(externalId.toString())
    identifiers.add(normalizedId.toString())
    // Keep the collector's ID as the synchronization external ID because
    // emitted relations reference it directly. The normalized ML-registry ID
    // remains an identifier, so it can still merge and be queried safely.
    type = "ml-registry.kubeflow".toString()
}

return Sts.createId(externalId.toString(), identifiers, type.toString())
