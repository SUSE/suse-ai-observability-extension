// Bridge ID Extractor for SUSE AI
// Creates relations between OTel resources and SUSE AI abstractions

if (topologyElement == null || topologyElement.externalId == null) {
    return null
}

def data = topologyElement.data ?: [:]
def tags = data.tags ?: [:]
def externalId = topologyElement.externalId.toString()

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

if (productName && !data.containsKey('sourceExternalId')) {
    // Store metadata for the template
    data.put('suseAiProductName', productName)
    data.put('suseAiProductType', productType)
    
    return Sts.createId('suse-ai:bridge:' + externalId, [] as Set, 'is')
}

return null
