def elementMap = element.asReadonlyMap()
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

if (!attributes.containsKey("gen_ai.system")) {
    return null
}

def data = component["data"] ?: [:]
if (data instanceof String) {
    try { data = new groovy.json.JsonSlurper().parseText(data) } catch (e) { data = [:] }
}

def labels = data["labels"] ?: []
if (!labels.contains("gen_ai_app")) { labels.add("gen_ai_app") }
data["labels"] = labels
data["domain"] = "urn:stackpack:open-telemetry:shared:domain:opentelemetry"
data["layer"] = "urn:stackpack:common:layer:services"

component["data"] = data
return component
