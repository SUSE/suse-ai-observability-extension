def elementMap = element.asReadonlyMap()
def payload = elementMap["payload"]
def componentPayload = payload ? (payload["TopologyComponent"] ?: payload["TopologyRelation"]) : elementMap
def dataStr = componentPayload["data"]
def attributes = [:]
def resourceAttributes = [:]
if (componentPayload["spanAttributes"]) {
    attributes = componentPayload["spanAttributes"]
    resourceAttributes = componentPayload["resourceAttributes"] ?: [:]
} else if (dataStr instanceof String) {
    try {
        def parsedData = new groovy.json.JsonSlurper().parseText(dataStr)
        attributes = parsedData["tags"] ?: [:]
        resourceAttributes = parsedData["tags"] ?: [:]
    } catch (e) {}
}
if (!attributes.containsKey("gen_ai.system")) {
    return null
}
def systemName = attributes.get("gen_ai.system", "Unknown System")
def clusterName = resourceAttributes.get("k8s.cluster.name", "local")
def namespace = resourceAttributes.get("k8s.namespace.name", resourceAttributes.get("service.namespace", "default"))
def appName = attributes.get("gen_ai.application_name", resourceAttributes.get("service.name", "unknown-app"))

def appUrn = (componentPayload["externalId"] ?: "urn:service:/${clusterName}:${namespace}:${appName}").toString()
def systemUrn = "urn:genai:system:/${systemName.toLowerCase()}".toString()

return [
    "sourceId": appUrn,
    "targetId": systemUrn,
    "externalId": "${appUrn}->${systemUrn}".toString(),
    "typeName": "uses"
]
