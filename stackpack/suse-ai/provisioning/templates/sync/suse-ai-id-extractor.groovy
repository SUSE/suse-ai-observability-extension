element = topologyElement.asReadonlyMap()
externalId = element["externalId"]
typeName = element["typeName"]
data = element["data"]

identifiers = new HashSet()
if (data.containsKey("identifiers") && data["identifiers"] instanceof List) {
    data["identifiers"].each { identifiers.add(it.toString()) }
}

// Check for SUSE AI management
boolean isManaged = false
if (data.containsKey("tags") && data["tags"] instanceof Map) {
    def tags = data["tags"]
    if (tags["suse.ai.managed"] == "true" || tags["suse.ai.managed"] == true) {
        isManaged = true
    }
}

if (isManaged) {
    // Add original externalId to identifiers to ensure we can link back for metrics/traces
    identifiers.add(externalId.toString())
    // Create a new prefixed externalId to avoid ownership conflict with OTel sync
    externalId = "suse-ai:" + externalId
}

return Sts.createId(externalId.toString(), identifiers, typeName.toString())
