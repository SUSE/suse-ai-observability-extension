// IdExtractorFunction for SUSE AI components and relations
// Adds a 'suse-ai:' prefix to component externalIds to keep them
// separate from the standard OTel StackPack components.
// The original OTel externalId is kept as an identifier to enable
// cross-stackpack merging and relation source/target resolution.

if (topologyElement == null) {
    return null
}

def elementMap = topologyElement.asReadonlyMap()
def externalId = elementMap["externalId"]
if (externalId == null) {
    return null
}

def extIdStr = externalId.toString()
def typeName = (elementMap["typeName"] ?: 'unknown').toString().toLowerCase()

// Detect relation elements: they have sourceExternalId at the top level
// (NOT inside the data map). Relations must be processed so that the
// sync can create topology connections.
def isRelation = elementMap.containsKey('sourceExternalId')

if (!isRelation) {
    // --- Component processing ---

    def data = elementMap["data"] ?: [:]
    def tags = data["tags"] ?: [:]

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

    // Components with suse.ai.component.name are handled by the
    // "SUSE AI Products" sync (aggregation). Skip them here.
    if (normalizedTags.containsKey('suse.ai.component.name')) {
        return null
    }

    // Only process elements with AI-related tags
    boolean hasAiTags = normalizedTags.keySet().any { tag ->
        def t = tag.toString().toLowerCase()
        t.contains('suse.ai') || t.startsWith('gen_ai.')
    }
    if (!hasAiTags) {
        return null
    }

    // Collect additional identifiers from the data
    def identifiers = new HashSet()
    if (data.containsKey("identifiers") && data["identifiers"] instanceof List) {
        data["identifiers"].each { id -> identifiers.add(id) }
    }
    // Add the original OTel externalId so that:
    // 1. Relations can resolve source/target (they reference unprefixed OTel URNs)
    // 2. Cross-stackpack merging works with the OTel StackPack
    identifiers.add(extIdStr)

    def newExternalId = 'suse-ai:' + extIdStr
    return Sts.createId(newExternalId, identifiers, typeName)
} else {
    // --- Relation processing ---
    // Use the original externalId (no prefix needed for relations).
    // The system resolves sourceId/targetId by matching against
    // component externalIds and identifiers.
    return Sts.createId(extIdStr, new HashSet(), typeName)
}
