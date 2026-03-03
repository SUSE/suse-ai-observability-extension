// IdExtractorFunction for SUSE AI components
// It mirrors OTel elements by adding a 'suse-ai:' prefix
// This creates a separate graph structure for AI observability

if (topologyElement == null) {
    return null
}

def data = topologyElement.data ?: [:]
def tags = data.tags ?: [:]
def externalId = topologyElement.externalId
if (externalId == null) {
    return null
}

def extIdStr = externalId.toString()
def typeName = topologyElement.type?.name?.toString() ?: 'unknown'

// Normalize tags to map for easier checking
def normalizedTags = [:]
if (tags instanceof List) {
    tags.each { tag ->
        if (tag instanceof String) {
            def parts = tag.split(':', 2)
            if (parts.length == 2) {
                normalizedTags[parts[0]] = parts[1]
            } else {
                normalizedTags[tag] = true
            }
        }
    }
} else if (tags instanceof Map) {
    normalizedTags = tags
}

// DUPLICATION FIX (Option B): If a component has a 'suse.ai.component.name' tag, 
// it will be handled by the "SUSE AI Products" sync (Aggregation).
// We should NOT create a mirrored instance here to avoid duplicates.
if (normalizedTags.containsKey('suse.ai.component.name')) {
    return null
}

// Only process elements that are relevant to services or relations
// This avoids duplicating low-level infra like processes if not needed
if (typeName != 'service' && typeName != 'service-instance' && typeName != 'pod' && 
    !data.containsKey('sourceExternalId')) {
    
    // Check if it has any AI tags even if it's not a service
    boolean hasAiTags = normalizedTags.keySet().any { tag -> tag.toString().toLowerCase().contains('suse.ai') }
    
    if (!hasAiTags) {
        return null
    }
}

def newExternalId = 'suse-ai:' + extIdStr
return Sts.createId(newExternalId, [] as Set, typeName)
