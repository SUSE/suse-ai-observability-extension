def elementMap = topologyElement.asReadonlyMap()
def payload = elementMap["payload"]
def component = payload ? (payload["TopologyComponent"] ?: payload["TopologyRelation"]) : elementMap
def dataStr = component["data"]
def attributes = [:]

if (component["spanAttributes"]) {
    attributes = component["spanAttributes"]
} else if (dataStr instanceof String) {
    try {
        def parsedData = new groovy.json.JsonSlurper().parseText(dataStr)
        attributes = parsedData["tags"] ?: [:]
    } catch (e) {}
} else if (dataStr instanceof Map) {
    attributes = dataStr["tags"] ?: [:]
}

def systemName = (attributes["gen_ai.system"] ?: attributes["db.system"])?.toString()
def modelName = (attributes["gen_ai.request.model"] ?: attributes["model_name"])?.toString()

if (!systemName || !modelName) return null

def systemLower = systemName.toLowerCase().toString()
def modelUrn = "openlit:urn:genai:model:/${systemLower}/${modelName.toLowerCase()}".toString()

return Sts.createId(modelUrn, new HashSet(), "service")
