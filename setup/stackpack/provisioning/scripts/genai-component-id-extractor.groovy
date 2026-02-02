def elementMap = topologyElement.asReadonlyMap()
def payload = elementMap["payload"]
def component = payload ? (payload["TopologyComponent"] ?: payload["TopologyRelation"]) : elementMap

def externalId = component["externalId"]
if (!externalId && component.containsKey("spanId")) {
    externalId = component["spanId"]
}
def type = component["typeName"]?.toLowerCase() ?: "unknown"
def data = component["data"] ?: [:]
def identifiers = new HashSet()

if (data instanceof String) {
    try {
        def parsedData = new groovy.json.JsonSlurper().parseText(data)
        if (parsedData.containsKey("identifiers") && parsedData["identifiers"] instanceof List) {
            parsedData["identifiers"].each { identifiers.add(it) }
        }
    } catch (e) {}
} else if (data instanceof Map) {
    if (data.containsKey("identifiers") && data["identifiers"] instanceof List) {
        data["identifiers"].each { identifiers.add(it) }
    }
}

if (externalId && externalId.startsWith("urn:")) {
    identifiers.add(externalId)
}
return Sts.createId(externalId ?: "unknown-id", identifiers, type)
