def elementMap = topologyElement.asReadonlyMap()
def payload = elementMap["payload"]
def component = payload ? (payload["TopologyComponent"] ?: payload["TopologyRelation"]) : elementMap

def externalId = component["externalId"] ?: component["spanId"]
if (!externalId) return null

def newExternalId = "openlit:system:${externalId}".toString()
return Sts.createId(newExternalId, new HashSet(), "service")
