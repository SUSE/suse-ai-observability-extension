def elementMap = element.asReadonlyMap()
def payload = elementMap["payload"]
def relationPayload = payload ? payload["TopologyRelation"] : elementMap

def sourceId = relationPayload["sourceId"]?.toString()
def targetId = relationPayload["targetId"]?.toString()

if (!sourceId || !targetId) return null

// In OTel topology:
// service (source) --[provided-by]--> service-instance (target)
// In our prefixed topology:
// openlit:app:<urn> --[provided-by]--> openlit:system:<urn>

return [
    "sourceId": "openlit:app:${sourceId}".toString(),
    "targetId": "openlit:system:${targetId}".toString(),
    "externalId": "openlit:${relationPayload['externalId'] ?: sourceId + '->' + targetId}".toString(),
    "typeName": (relationPayload["typeName"] ?: "provided-by").toString()
]
