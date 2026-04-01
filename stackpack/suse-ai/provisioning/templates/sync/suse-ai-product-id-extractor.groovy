// Product ID Extractor for SUSE AI
// Creates a single logical component for each named AI product
// (e.g., all Milvus instances merge into one 'Milvus' component)
//
// Cross-sync linking: adds both the urn:suse-ai:-prefixed and the
// unprefixed OTel externalId as identifiers so that:
// 1. The product component merges with the main sync component
//    (which has externalId urn:suse-ai:<otel-urn>)
// 2. Relation source/target resolution works (relations reference
//    unprefixed OTel URNs)

if (topologyElement == null) {
    return null
}

def data = topologyElement.data ?: [:]
def tags = data.tags ?: [:]
def typeName = topologyElement.type?.name?.toString() ?: 'unknown'

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

if (productName) {
    // Create a deterministic ID for the product
    def newExternalId = "urn:suse-ai:product:${productType}:${productName}".toString()

    def identifiers = [newExternalId] as Set

    // Add urn:suse-ai:-prefixed OTel externalId so this product component
    // merges with the main sync component (which has externalId urn:suse-ai:<urn>).
    // Do NOT add the unprefixed OTel URN — that would cause merging with
    // the OTel StackPack's service component, breaking type and monitors.
    def originalExternalId = topologyElement.externalId?.toString()
    if (originalExternalId) {
        identifiers.add("urn:suse-ai:${originalExternalId}".toString())
    }

    // Determine specific product type based on product name
    def specificType = productType
    def productNameLower = productName?.toString()?.toLowerCase()
    switch(productNameLower) {
        case 'vllm':
        case 'ollama':
            specificType = "inference-engine.${productNameLower}"
            break
        case 'qdrant':
        case 'milvus':
            specificType = "vectordb.${productNameLower}"
            break
        case 'opensearch':
        case 'elasticsearch':
            specificType = "search-engine.${productNameLower}"
            break
        case 'open-webui':
        case 'open webui':
            specificType = "ui.open-webui"
            break
        case 'litellm':
            specificType = "model-proxy.litellm"
            break
        case 'mlflow':
            specificType = "ml-registry.mlflow"
            break
    }

    return Sts.createId(newExternalId, identifiers, specificType)
}

return null
