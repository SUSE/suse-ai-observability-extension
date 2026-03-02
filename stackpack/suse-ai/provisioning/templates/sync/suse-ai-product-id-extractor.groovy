// Product ID Extractor for SUSE AI
// Creates a single logical component for each named AI product
// (e.g., all Milvus instances merge into one 'Milvus' component)

if (topologyElement == null) {
    return null
}

def data = topologyElement.data ?: [:]
def tags = data.tags ?: [:]
def typeName = topologyElement.type?.name?.toString() ?: "unknown"

// Normalize tags to map
def normalizedTags = [:]
if (tags instanceof List) {
    tags.each { 
        if (it instanceof String) {
            def parts = it.split(':', 2)
            if (parts.length == 2) normalizedTags[parts[0]] = parts[1]
            else normalizedTags[it] = true
        }
    }
} else if (tags instanceof Map) {
    normalizedTags = tags
}

def productName = normalizedTags['suse.ai.component.name']?.toString()
def productType = normalizedTags['suse.ai.component.type']?.toString() ?: "application"

if (productName) {
    // Create a deterministic ID for the product
    def newExternalId = "suse-ai:product:${productType}:${productName}".toString()
    
    // Use the original OTel type if we want the mapper to handle it
    // Or just use 'application' as base
    return Sts.createId(newExternalId, new HashSet(), typeName)
}

return null
