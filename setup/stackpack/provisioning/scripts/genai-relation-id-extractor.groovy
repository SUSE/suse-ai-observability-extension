element = topologyElement.asReadonlyMap()

externalId = element["externalId"]
type = element["typeName"].toLowerCase()

return Sts.createId(externalId, new HashSet(), type)
