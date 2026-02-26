// IdExtractorFunction for SUSE AI components
// It ensures that SUSE AI components are separated from OTel components by adding a prefix
// But only for those that are specifically marked or inferred as AI components

if (topologyElement == null) {
    return null
}

def data = topologyElement.data ?: [:]
def externalId = topologyElement.externalId

if (externalId == null) {
    return null
}

def extIdStr = externalId.toString()

// Check for SUSE AI management
boolean isManaged = false
def rawTags = data.tags

if (rawTags instanceof Map) {
    if (rawTags.containsKey("suse.ai.managed") || rawTags["telemetry.sdk.name"] == "suse-ai" || rawTags.keySet().any { it.toString().contains("suse.ai") }) {
        isManaged = true
    }
} else if (rawTags instanceof List) {
    if (rawTags.any { it.toString().contains("suse.ai") || it.toString().contains("telemetry.sdk.name:suse-ai") }) {
        isManaged = true
    }
}

// Special case for Open WebUI
if (extIdStr.contains("Open WebUI")) {
    isManaged = true
}

if (isManaged) {
    def newExternalId = "suse-ai:" + extIdStr
    return Sts.createId(newExternalId, new HashSet(), topologyElement.type?.name?.toString() ?: "unknown")
}

return null
