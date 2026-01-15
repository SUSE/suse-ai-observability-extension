element = topologyElement.asReadonlyMap()

externalId = element["externalId"]
type = element["typeName"].toLowerCase()
data = element["data"]

identifiers = new HashSet()

if(data.containsKey("identifiers") && data["identifiers"] instanceof List<String>) {
    data["identifiers"].each{ id ->
        identifiers.add(id)
    }
}

return Sts.createId(externalId, identifiers, type)
