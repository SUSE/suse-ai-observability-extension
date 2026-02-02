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
if (!attributes.containsKey("gen_ai.system") || !attributes.containsKey("gen_ai.request.model")) {
    return null
}
def systemName = attributes["gen_ai.system"]
def modelName = attributes["gen_ai.request.model"]
def modelUrn = "urn:genai:model:/${systemName.toLowerCase()}/${modelName.toLowerCase()}"
return [
    "externalId": modelUrn,
    "typeName": "genai.model",
    "data": [
        "name": modelName,
        "tags": [
            "genai_model": modelName,
            "genai_system": systemName,
            "stackpack": "openlit"
        ],
        "domain": "urn:stackpack:open-telemetry:shared:domain:opentelemetry",
        "layer": "urn:stackpack:common:layer:services"
    ]
]
