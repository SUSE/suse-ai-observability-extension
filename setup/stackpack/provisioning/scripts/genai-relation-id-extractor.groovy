def elementMap = topologyElement.asReadonlyMap()
def payload = elementMap["payload"]
def relation = payload ? payload["TopologyRelation"] : elementMap
def externalId = relation["externalId"]
def type = relation["typeName"]?.toLowerCase() ?: "unknown"
return Sts.createId(externalId ?: "unknown-rel", new HashSet(), type)
