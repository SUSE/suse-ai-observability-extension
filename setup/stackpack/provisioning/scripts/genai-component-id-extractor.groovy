def elementMap = topologyElement.asReadonlyMap()
def payload = elementMap["payload"]
def component = payload ? (payload["TopologyComponent"] ?: payload["TopologyRelation"]) : elementMap

def type = (component["typeName"] ?: elementMap["typeName"] ?: "unknown").toString().toLowerCase()
if (type != "service" && type != "service-instance") {
    return null
}

def externalId = (component["externalId"] ?: component["spanId"])?.toString()
if (!externalId) return null

def prefix = "openlit:"
if (type == "service") {
    prefix = "openlit:app:"
} else if (type == "service-instance") {
    prefix = "openlit:system:"
}

def newExternalId = externalId.startsWith("openlit:") ? externalId : "${prefix}${externalId}".toString()

return Sts.createId(newExternalId, new HashSet(), type)
