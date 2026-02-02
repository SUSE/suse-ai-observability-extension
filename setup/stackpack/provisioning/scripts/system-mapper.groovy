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
}
if (!attributes.containsKey("gen_ai.system")) {
    return null
}
def systemName = attributes["gen_ai.system"]
def systemUrn = "urn:genai:system:/${systemName.toLowerCase()}"
return [
    "externalId": systemUrn,
    "typeName": "genai.system.${systemName.toLowerCase()}",
    "data": [
        "name": systemName,
        "tags": [
            "gen_ai_system": "true",
            "gen_ai.system": systemName,
            "stackpack": "openlit"
        ],
        "domain": "urn:stackpack:open-telemetry:shared:domain:opentelemetry",
        "layer": "urn:stackpack:common:layer:services"
    ]
]
