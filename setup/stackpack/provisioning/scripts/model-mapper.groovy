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

def systemName = (attributes["gen_ai.provider.name"] ?: attributes["gen_ai.system"] ?: attributes["db.system"])?.toString()
def modelAttr = (attributes["gen_ai.request.model"] ?: attributes["gen_ai.models"])?.toString()

// If we have a list of models in gen_ai.models, we'd ideally emit one per model
// But the multiplexed sync gives us the payload once. 
// For now we take the first model or the specific one from span attributes.
def modelName = "default-model"
if (modelAttr) {
    modelName = modelAttr.split(",")[0].trim()
}

if (!systemName) {
    def serviceName = (attributes["service.name"] ?: componentPayload["name"])?.toString()
    if (serviceName?.toLowerCase()?.contains("milvus")) systemName = "milvus"
    else if (serviceName?.toLowerCase()?.contains("ollama")) systemName = "ollama"
}

if (!systemName) return null

def systemLower = systemName.toLowerCase().toString()
def modelUrn = "openlit:urn:genai:model:/${systemLower}/${modelName.toLowerCase()}".toString()

element.type.name = "urn:stackpack:openlit:shared:component-type:genai-model"
if (!element.data.containsKey("tags")) element.data.put("tags", [:])
element.data.put("name", modelName)
element.data.put("externalId", modelUrn)
element.data.tags.putAll(attributes)
element.data.tags.put("genai-model", "true")
element.data.tags.put("gen_ai_app", "true")
element.data.tags.put("stackpack", "suse-ai")

return element
