def elementMap = topologyElement.asReadonlyMap()
def type = elementMap["typeName"]?.toString()?.toLowerCase() ?: ""

if (type != "service" && type != "service-instance") {
    return null
}

def externalId = elementMap["externalId"]?.toString()
if (!externalId) {
    return null
}

def prefix = "openlit:"
if (type == "service") {
    prefix = "openlit:app:"
} else if (type == "service-instance") {
    prefix = "openlit:system:"
}

def newExternalId = externalId.startsWith("openlit:") ? externalId : "${prefix}${externalId}".toString()

return Sts.createId(newExternalId, new java.util.HashSet(), type)
