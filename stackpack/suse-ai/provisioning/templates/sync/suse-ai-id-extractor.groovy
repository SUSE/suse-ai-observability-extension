// IdExtractorFunction for SUSE AI components
// It mirrors OTel elements by adding a 'suse-ai:' prefix
// This creates a separate graph structure for AI observability

if (topologyElement == null) {
    return null
}

def externalId = topologyElement.externalId
if (externalId == null) {
    return null
}

def extIdStr = externalId.toString()
def typeName = topologyElement.type?.name?.toString() ?: "unknown"

// Only process elements that are relevant to services or relations
// This avoids duplicating low-level infra like processes if not needed
if (typeName != "service" && typeName != "service-instance" && typeName != "pod" && 
    !topologyElement.data?.containsKey("sourceExternalId")) {
    // Check if it has AI tags even if it's not a service
    def tags = topologyElement.data?.tags
    boolean hasAiTags = false
    if (tags instanceof Map) {
        hasAiTags = tags.keySet().any { it.toString().contains("suse.ai") }
    } else if (tags instanceof List) {
        hasAiTags = tags.any { it.toString().contains("suse.ai") }
    }
    
    if (!hasAiTags) return null
}

def newExternalId = "suse-ai:" + extIdStr
return Sts.createId(newExternalId, new HashSet(), typeName)
