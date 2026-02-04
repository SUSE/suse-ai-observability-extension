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
def namespace = (attributes["service.namespace"] ?: "default").toString()

if (!systemName) return null

// We assume the system is a service in the same namespace
// This is a heuristic for inference.
def systemUrn = "urn:opentelemetry:namespace/${namespace}:service/${systemName.toLowerCase()}".toString()
def targetId = "openlit:system:${systemUrn}".toString()
def appUrn = element.externalId.toString()

if (!appUrn.startsWith("openlit:app:")) return null

return [
    "sourceId": appUrn,
    "targetId": targetId,
    "externalId": "${appUrn}->${targetId}".toString(),
    "typeName": "uses"
]
