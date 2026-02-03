def elementMap = element.asReadonlyMap()
def payload = elementMap["payload"]
def relationPayload = payload ? (payload["TopologyRelation"]) : elementMap

if (!relationPayload) return null

def sourceId = relationPayload["sourceId"]?.toString()
def targetId = relationPayload["targetId"]?.toString()
def externalId = relationPayload["externalId"]?.toString()

if (!sourceId || !targetId) return null

// Apply CONSISTENT prefix to match our components
def newSourceId = "openlit:${sourceId}".toString()
def newTargetId = "openlit:${targetId}".toString()
def newExternalId = "openlit:${externalId ?: sourceId + '->' + targetId}".toString()

return [
    "sourceId": newSourceId,
    "targetId": newTargetId,
    "externalId": newExternalId,
    "typeName": "uses".toString()
]
