def elementMap = topologyElement.asReadonlyMap()
def payload = elementMap["payload"]
def component = payload ? (payload["TopologyComponent"] ?: payload["TopologyRelation"]) : elementMap

def externalId = (component["externalId"] ?: component["spanId"])?.toString()
if (!externalId) return null

def type = component["typeName"]?.toLowerCase() ?: "unknown"
// Add openlit: prefix to avoid claim conflicts with standard OTel sync
def newExternalId = "openlit:${externalId}".toString()

return Sts.createId(newExternalId, new HashSet(), type)
