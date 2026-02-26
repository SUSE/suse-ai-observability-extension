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

// Ensure the managed tag is present if we are here
tags['suse.ai.managed'] = 'true'

// Determine component type
def currentType = element.type?.name ?: "application"

if (tags['suse.ai.component.type']) {
    currentType = tags['suse.ai.component.type'].toString()
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
}

// Default to application if type is unknown
def knownTypes = ['application', 'agent', 'ui', 'inference-engine', 'vectordb', 'genai.model', 'model-proxy', 'search-engine', 'mcp-server', 'workflow-engine', 'ml-registry']
if (!knownTypes.contains(currentType)) {
    currentType = 'application'
}

element.type.name = currentType
data.tags = tags
element.data = data

element
