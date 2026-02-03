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

String systemName = (attributes["gen_ai.system"] ?: attributes["db.system"])?.toString()
if (!systemName) {
    def serviceName = (attributes["service.name"] ?: componentPayload["name"])?.toString()
    if (serviceName?.toLowerCase()?.contains("milvus")) systemName = "milvus"
    else if (serviceName?.toLowerCase()?.contains("opensearch")) systemName = "opensearch"
    else if (serviceName?.toLowerCase()?.contains("ollama")) systemName = "ollama"
    else if (serviceName?.toLowerCase()?.contains("vllm")) systemName = "vllm"
}

if (!systemName) return null

def systemLower = systemName.toLowerCase().toString()
boolean isDB = attributes.containsKey("db.system") || systemLower.contains("milvus") || systemLower.contains("opensearch")

def systemUrn = "openlit:" + (isDB ? "urn:openlit:vectordb:system/${systemLower}" : "urn:genai:system:/${systemLower}").toString()
def typeName = (isDB ? "dbsystem.${systemLower}" : "genai.system.${systemLower}").toString()
def label = (isDB ? "gen_vectordb_system" : "gen_ai_system").toString()

return [
    "externalId": systemUrn,
    "typeName": typeName,
    "data": [
        "name": systemName,
        "labels": [label, "stackpack:openlit", "gen_ai_app"],
        "domain": "urn:stackpack:open-telemetry:shared:domain:opentelemetry".toString(),
        "layer": "urn:stackpack:common:layer:services".toString()
    ]
]
