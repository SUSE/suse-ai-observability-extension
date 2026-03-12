def data = element.data ?: [:]
def rawTags = data.tags ?: [:]
def tags = [:]

// Convert list of tags to map for easier processing
if (rawTags instanceof List) {
    rawTags.each { 
        if (it instanceof String) {
            def parts = it.split(':', 2)
            if (parts.length == 2) {
                tags[parts[0].toString()] = parts[1].toString()
            } else {
                tags[it.toString()] = "true"
            }
        }
    }
} else if (rawTags instanceof Map) {
    rawTags.each { k, v ->
        tags[k.toString()] = v?.toString() ?: ""
    }
}

// Identity Promotion
if (tags.containsKey('suse.ai.component.name')) {
    data.put('name', tags['suse.ai.component.name'].toString())
} else if (tags.containsKey('service.name')) {
    data.put('name', tags['service.name'].toString())
}

// Identify if it is a managed SUSE AI Component
boolean isManaged = tags['suse.ai.managed'] == 'true' || 
                   tags['suse.ai.managed'] == "true" || 
                   tags['telemetry.sdk.name'] == 'suse-ai' ||
                   tags.keySet().any { it.toString().toLowerCase().startsWith('suse.ai.') }

// Determine component type
def currentType = element.type?.name?.toString() ?: "application"

if (isManaged) {
    tags['suse.ai.managed'] = 'true'
    
    if (tags['suse.ai.component.type']) {
        currentType = tags['suse.ai.component.type'].toString()
    } else if (tags.containsKey('gen_ai.system')) {
        currentType = 'inference-engine'
    }

    // Map common aliases
    def category = currentType
    switch(currentType.toLowerCase()) {
        case 'ui':
        case 'frontend':
            category = 'ui'
            break
        case 'app':
        case 'application':
        case 'service':
            category = 'application'
            break
        case 'agent':
            category = 'agent'
            break
        case 'llm':
        case 'model':
        case 'llm-model':
            category = 'llm-model'
            break
        case 'db':
        case 'vectordb':
        case 'vector-db':
            category = 'vectordb'
            break
    }
    
    // UI DUPLICATION FIX:
    // Only add the category label to logical PRODUCT components.
    // This hides mirrored instances from the category menus (AI Applications, etc.)
    // but keeps the logical products visible.
    def extId = element.externalId?.toString() ?: ""
    if (extId.startsWith("suse-ai:product:")) {
        tags['suse.ai.category'] = category.toString()
    }
    
    currentType = category

    // Product-specific specialization
    def productName = tags['suse.ai.component.name']?.toString()?.toLowerCase()
    if (productName) {
        switch(productName) {
            case 'vllm':
            case 'ollama':
                currentType = "inference-engine.${productName}".toString()
                break
            case 'qdrant':
            case 'milvus':
                currentType = "vectordb.${productName}".toString()
                break
            case 'opensearch':
            case 'elasticsearch':
                currentType = "search-engine.${productName}".toString()
                break
            case 'open-webui':
            case 'open webui':
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
    
    // Provider-specific specialization for llm-model
    if (currentType == 'llm-model' && tags['gen_ai.provider.name']) {
        def provider = tags['gen_ai.provider.name'].toString().toLowerCase()
        switch(provider) {
            case 'ollama':
                currentType = "llm-model.ollama"
                break
            case 'vllm':
                currentType = "llm-model.vllm"
                break
        }
    }

    // Default to application if type is unknown among our AI types
    def aiTypes = ['application', 'agent', 'ui', 'inference-engine', 'vectordb', 'llm-model', 'model-proxy', 'search-engine', 'mcp-server', 'workflow-engine', 'ml-registry']
    if (!aiTypes.contains(currentType) && !currentType.contains('.')) {
        currentType = 'application'
    }
}

element.type.name = currentType.toString()
data.tags = tags
element.data = data

element
