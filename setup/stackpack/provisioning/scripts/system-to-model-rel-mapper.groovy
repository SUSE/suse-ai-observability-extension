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

if (!systemName || !modelAttr) return null

def systemUrn = element.externalId.toString()

if (!systemUrn.startsWith("openlit:system:")) return null

def models = modelAttr.split(",")

// Emit relations for all models
// Note: In a multiplexed sync, we can only emit ONE object per action normally.
// But if we return a list, the sync engine might support it?
// Actually, standard behavior is one. 
// For now we emit one for the first model.
def modelName = models[0].trim()
def systemLower = systemName.toLowerCase().toString()
def modelUrn = "openlit:urn:genai:model:/${systemLower}/${modelName.toLowerCase()}".toString()

return [
    "sourceId": systemUrn,
    "targetId": modelUrn,
    "externalId": "${systemUrn}->${modelUrn}".toString(),
    "typeName": "runs"
]
