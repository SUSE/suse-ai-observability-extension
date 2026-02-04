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

def operationName = (attributes["gen_ai.operation.name"] ?: attributes["db.operation"])?.toString()
if (!operationName) return null

def systemName = (attributes["gen_ai.system"] ?: attributes["db.system"] ?: "unknown").toString()
def modelName = (attributes["gen_ai.request.model"] ?: attributes["model_name"] ?: "none").toString()

def systemLower = systemName.toLowerCase().toString()
def operationUrn = "openlit:urn:genai:operation:/${systemLower}/${modelName.toLowerCase()}/${operationName.toLowerCase()}".toString()

return [
    "externalId": operationUrn,
    "typeName": "genai.operation",
    "data": [
        "name": operationName,
        "tags": [
            "genai_operation": "true",
            "stackpack": "openlit",
            "gen_ai_app": "true",
            "gen_ai_system": systemName,
            "gen_ai_request_model": modelName,
            "name": operationName
        ],
        "domain": "urn:stackpack:open-telemetry:shared:domain:opentelemetry".toString(),
        "layer": "urn:stackpack:common:layer:services".toString()
    ]
]
