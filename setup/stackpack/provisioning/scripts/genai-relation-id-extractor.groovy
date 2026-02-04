def elementMap = topologyElement.asReadonlyMap()
def payload = elementMap["payload"]
def isRelation = payload?.containsKey("TopologyRelation")
def component = isRelation ? payload["TopologyRelation"] : (payload?.get("TopologyComponent") ?: elementMap)

def externalId = component["externalId"]?.toString()
if (!externalId) {
    externalId = component["spanId"]?.toString()
}

def type = component["typeName"]?.toLowerCase() ?: "uses"

// Add openlit: prefix
def newExternalId = externalId?.startsWith("openlit:") ? externalId : "openlit:${externalId ?: "unknown-rel"}".toString()

// Ensure inferred relations don't clash with components
if (!isRelation) {
    newExternalId = "rel:${newExternalId}".toString()
}

return Sts.createId(newExternalId, new HashSet(), type)
