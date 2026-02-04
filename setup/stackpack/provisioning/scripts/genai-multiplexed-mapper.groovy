def elementMap = element.asReadonlyMap()
def payload = elementMap["payload"]
def componentPayload = payload ? (payload["TopologyComponent"] ?: payload["TopologyRelation"]) : elementMap
def dataStr = componentPayload["data"]
def attributes = [:]

if (componentPayload["spanAttributes"]) {
    attributes = componentPayload["spanAttributes"]
} else if (dataStr instanceof String) {
    try {
        def parsedData = new groovy.json.JsonSlurper().parseText(dataStr)
        attributes = parsedData["tags"] ?: [:]
    } catch (e) {}
} else if (dataStr instanceof Map) {
    attributes = dataStr["tags"] ?: [:]
}

def externalId = element.externalId.toString()
def serviceName = (attributes["service.name"] ?: componentPayload["name"])?.toString()
def systemName = (attributes["gen_ai.provider.name"] ?: attributes["gen_ai.system"] ?: attributes["db.system"])?.toString()

if (!systemName && serviceName) {
    def lowerName = serviceName.toLowerCase()
    if (lowerName.contains("milvus")) systemName = "milvus"
    else if (lowerName.contains("ollama")) systemName = "ollama"
    else if (lowerName.contains("vllm")) systemName = "vllm"
    else if (lowerName.contains("openai")) systemName = "openai"
    else if (lowerName.contains("opensearch")) systemName = "opensearch"
}

if (externalId.startsWith("openlit:system:")) {
    if (!systemName) return null
    
    // Transform to System
    def systemLower = systemName.toLowerCase().toString()
    boolean isDB = attributes.containsKey("db.system") || systemLower.contains("milvus") || systemLower.contains("opensearch")
    def typeUrn = (isDB ? "urn:stackpack:openlit:shared:component-type:dbsystem-${systemLower}" : "urn:stackpack:openlit:shared:component-type:genai-system-${systemLower}").toString()
    element.type.name = typeUrn
    
    def label = (isDB ? "gen_vectordb_system" : "gen_ai_system").toString()
    if (!element.data.containsKey("tags")) element.data.put("tags", [:])
    element.data.put("name", systemName)
    element.data.tags.putAll(attributes)
    element.data.tags.put(label, "true")
    element.data.tags.put("gen_ai_app", "true")
    element.data.tags.put("stackpack", "suse-ai")
} else {
    // Keep as App
    element.type.name = "urn:stackpack:openlit:shared:component-type:genai-app"
    if (!element.data.containsKey("tags")) element.data.put("tags", [:])
    element.data.tags.putAll(attributes)
    element.data.tags.put("gen_ai_app", "true")
    element.data.tags.put("stackpack", "suse-ai")
}

return element
