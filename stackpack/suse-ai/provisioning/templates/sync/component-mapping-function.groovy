def data = element.data ?: [:]
def rawTags = data.tags ?: [:]
def tags = [:]

// Convert list of tags to map for easier processing
if (rawTags instanceof List) {
    rawTags.each { 
        if (it instanceof String) {
            def parts = it.split(':', 2)
            if (parts.length == 2) {
                tags[parts[0]] = parts[1]
            } else {
                tags[it] = true
            }
        }
    }
} else if (rawTags instanceof Map) {
    tags = rawTags
}

// Identity Promotion
if (tags.containsKey('suse.ai.component.name')) {
    data.put('name', tags['suse.ai.component.name'].toString())
} else if (tags.containsKey('service.name')) {
    data.put('name', tags['service.name'].toString())
}

// Identify if it is a managed SUSE AI Component
boolean isManaged = tags['suse.ai.managed'] == 'true' || 
                   tags['suse.ai.managed'] == true || 
                   tags['telemetry.sdk.name'] == 'suse-ai' ||
                   tags.keySet().any { it instanceof String && it.startsWith('suse.ai.') }

// Determine component type
def currentType = element.type?.name ?: "application"

if (isManaged) {
    tags['suse.ai.managed'] = 'true'
    
    if (tags['suse.ai.component.type']) {
        currentType = tags['suse.ai.component.type'].toString()
    } else if (tags.containsKey('gen_ai.system')) {
        currentType = 'inference-engine'
    }

    // Map common aliases
    switch(currentType) {
        case 'ui':
        case 'frontend':
            currentType = 'ui'
            break
        case 'app':
        case 'service':
            currentType = 'application'
            break
        case 'llm':
        case 'model':
            currentType = 'genai.model'
            break
        case 'db':
        case 'vector-db':
            currentType = 'vectordb'
            break
    }

    // Product-specific specialization
    def productName = tags['suse.ai.component.name']?.toString()?.toLowerCase()
    if (productName) {
        switch(productName) {
            case 'vllm':
            case 'ollama':
                currentType = "inference-engine.${productName}"
                break
            case 'qdrant':
            case 'milvus':
                currentType = "vectordb.${productName}"
                break
            case 'opensearch':
                currentType = "search-engine.${productName}"
                break
            case 'open-webui':
                currentType = "ui.open-webui"
                break
            case 'litellm':
                currentType = "model-proxy.litellm"
                break
            case 'mlflow':
                currentType = "ml-registry.mlflow"
                break
        }
    }
    
    // Default to application if type is unknown among our AI types
    def aiTypes = ['application', 'agent', 'ui', 'inference-engine', 'vectordb', 'genai.model', 'model-proxy', 'search-engine', 'mcp-server', 'workflow-engine', 'ml-registry']
    if (!aiTypes.contains(currentType) && !currentType.contains('.')) {
        currentType = 'application'
    }
} else {
    // For non-managed mirrored components, keep original OTel types if possible
    // This ensures relations (vLLM -> Service) still work
}

element.type.name = currentType
data.tags = tags
element.data = data

element
