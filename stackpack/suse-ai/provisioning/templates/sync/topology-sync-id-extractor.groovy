// Passthrough ID extractor for the topology sync.
// Uses externalId as-is and reads identifiers from data.identifiers.

element = topologyElement.asReadonlyMap()

externalId = element["externalId"]
type = element["typeName"].toLowerCase()
data = element["data"]

identifiers = new HashSet()

if (data.containsKey("identifiers") && data["identifiers"] instanceof List) {
    data["identifiers"].each { id ->
        identifiers.add(id)
    }
}

return Sts.createId(externalId, identifiers, type)
