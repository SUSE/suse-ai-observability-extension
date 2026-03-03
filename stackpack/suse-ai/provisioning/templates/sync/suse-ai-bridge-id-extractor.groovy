// Bridge ID Extractor for SUSE AI
// Creates relations between OTel resources and SUSE AI abstractions

if (topologyElement == null) {
    return null
}

def data = topologyElement.data ?: [:]
def tags = data.tags ?: [:]
def externalId = topologyElement.externalId?.toString()

if (!externalId) {
    return null
}

// Normalize tags to map
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

def productName = normalizedTags['suse.ai.component.name']?.toString()
def productType = normalizedTags['suse.ai.component.type']?.toString() ?: 'application'

// If this is a component element (it doesn't have source/target in data)
// AND it belongs to a SUSE AI product, create a relation ID for it.
if (productName && !data.containsKey('sourceExternalId')) {
    def relationExternalId = 'suse-ai:bridge:' + externalId
    
    // Store metadata for the template
    data.put('suseAiProductName', productName)
    data.put('suseAiProductType', productType)
    
    return Sts.createId(relationExternalId, [] as Set, 'is')
}

return null
