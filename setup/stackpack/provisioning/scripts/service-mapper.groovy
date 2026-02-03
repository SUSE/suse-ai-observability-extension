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

def serviceName = (attributes["service.name"] ?: componentPayload["name"] ?: attributes["gen_ai.application_name"] ?: "GenAI Service").toString()

// Identification
boolean isMilvus = (serviceName?.toLowerCase()?.contains("milvus") || attributes["db.system"] == "milvus")
boolean isOllama = (serviceName?.toLowerCase()?.contains("ollama") || attributes["gen_ai.system"] == "ollama")
boolean isVllm = (serviceName?.toLowerCase()?.contains("vllm") || attributes["gen_ai.system"] == "vllm")
boolean isGenAi = attributes.containsKey("gen_ai.system") || attributes.containsKey("db.system") || isMilvus || isOllama || isVllm

if (!isGenAi) return null

// Modify element directly like OTel does
if (!element.data.containsKey("tags")) {
    element.data.put("tags", [:])
}
element.data.put("name", serviceName)
element.data.tags.putAll(attributes ?: [:])
element.data.tags.put("gen_ai_app", "true")
element.data.tags.put("stackpack", "openlit")
if (isMilvus) element.data.tags.put("gen_vectordb_system", "true")
if (isOllama || isVllm) element.data.tags.put("gen_ai_system", "true")

return element
