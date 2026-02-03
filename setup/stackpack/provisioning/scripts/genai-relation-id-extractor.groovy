def elementMap = topologyElement.asReadonlyMap()
def payload = elementMap["payload"]
def relation = payload ? payload["TopologyRelation"] : elementMap

if (!relation) return null

def externalId = relation["externalId"]?.toString()
def type = relation["typeName"]?.toLowerCase() ?: "uses"
// Add openlit: prefix to match our components
def newExternalId = "openlit:${externalId ?: "unknown-rel"}".toString()

return Sts.createId(newExternalId, new HashSet(), type)
