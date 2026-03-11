// Product ID Extractor for SUSE AI
// Creates a single logical component for each named AI product
// (e.g., all Milvus instances merge into one 'Milvus' component)
//
// Cross-stackpack linking: adds the suse-ai:-prefixed OTel externalId
// as an identifier so that relations created by the main sync
// (which use suse-ai:<otel-urn> for source/target) can resolve
// to these product components.

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
    def newExternalId = "suse-ai:product:${productType}:${productName}".toString()

    // Add the external ID as an identifier so monitors can find it
    def identifiers = [newExternalId] as Set

    // Cross-stackpack linking: add the suse-ai:-prefixed original OTel
    // externalId so that relations from the main sync can resolve to
    // this product component. The main sync creates relations like:
    //   source: suse-ai:urn:opentelemetry:namespace/X:service/Y
    //   target: suse-ai:urn:opentelemetry:namespace/X:service/Z
    // By adding this identifier, the system can match the relation
    // endpoints to the product component.
    def originalExternalId = topologyElement.externalId?.toString()
    if (originalExternalId) {
        identifiers.add("suse-ai:${originalExternalId}".toString())
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
