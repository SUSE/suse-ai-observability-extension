def elementMap = element.asReadonlyMap()
def payload = elementMap["payload"]
def componentPayload = payload ? (payload["TopologyComponent"] ?: payload["TopologyRelation"]) : elementMap
def dataStr = componentPayload["data"]
def attributes = [:]

if (componentPayload["spanAttributes"]) {
    attributes = componentPayload["spanAttributes"]
} else if (dataStr instanceof String) {
    try {
        def parsedData = new groovy.json.JsonSlurper().parseText(dataStr)
        attributes = parsedData["tags"] ?: [:]
    } catch (e) {}
} else if (dataStr instanceof Map) {
    attributes = dataStr["tags"] ?: [:]
}

def serviceName = (attributes["service.name"] ?: componentPayload["name"] ?: attributes["gen_ai.application_name"] ?: "GenAI Service").toString()

// Identification
boolean isMilvus = (serviceName?.toLowerCase()?.contains("milvus") || attributes["db.system"] == "milvus")
boolean isOllama = (serviceName?.toLowerCase()?.contains("ollama") || attributes["gen_ai.system"] == "ollama")
boolean isVllm = (serviceName?.toLowerCase()?.contains("vllm") || attributes["gen_ai.system"] == "vllm")
boolean isGenAi = attributes.containsKey("gen_ai.system") || attributes.containsKey("db.system") || isMilvus || isOllama || isVllm

if (!isGenAi) {
    // If it's a real relation from OTel, handle it simply
    def relationPayload = payload ? payload["TopologyRelation"] : null
    if (relationPayload) {
        def sourceId = relationPayload["sourceId"]?.toString()
        def targetId = relationPayload["targetId"]?.toString()
        if (sourceId && targetId) {
            return [
                "sourceId": "openlit:${sourceId}".toString(),
                "targetId": "openlit:${targetId}".toString(),
                "externalId": "openlit:${relationPayload['externalId'] ?: sourceId + '->' + targetId}".toString(),
                "typeName": (relationPayload["typeName"] ?: "uses").toString()
            ]
        }
    }
    return null
}

def results = []
def appUrn = element.externalId.toString()

def systemName = (attributes["gen_ai.system"] ?: attributes["db.system"])?.toString()
if (!systemName) {
    if (isMilvus) systemName = "milvus"
    else if (isOllama) systemName = "ollama"
    else if (isVllm) systemName = "vllm"
}

if (systemName) {
    def systemLower = systemName.toLowerCase().toString()
    boolean isDB = attributes.containsKey("db.system") || isMilvus
    def systemUrn = "openlit:" + (isDB ? "urn:openlit:vectordb:system/${systemLower}" : "urn:genai:system:/${systemLower}").toString()
    
    // Relation: App -> uses -> System
    results.add([
        "sourceId": appUrn,
        "targetId": systemUrn,
        "externalId": "${appUrn}->${systemUrn}".toString(),
        "typeName": "uses"
    ])
    
    // Model Inference
    def modelName = (attributes["gen_ai.request.model"] ?: attributes["model_name"])?.toString()
    if (modelName) {
        def modelUrn = "openlit:urn:genai:model:/${systemLower}/${modelName.toLowerCase()}".toString()
        
        // Relation: System -> runs -> Model
        results.add([
            "sourceId": systemUrn,
            "targetId": modelUrn,
            "externalId": "${systemUrn}->${modelUrn}".toString(),
            "typeName": "runs"
        ])
        
        // Relation: App -> uses -> Model
        results.add([
            "sourceId": appUrn,
            "targetId": modelUrn,
            "externalId": "${appUrn}->${modelUrn}".toString(),
            "typeName": "uses"
        ])
        
        // Operation Inference
        def operationName = (attributes["gen_ai.operation.name"] ?: attributes["db.operation"])?.toString()
        if (operationName) {
            def operationUrn = "openlit:urn:genai:operation:/${systemLower}/${modelName.toLowerCase()}/${operationName.toLowerCase()}".toString()
            
            // Relation: Model -> applies -> Operation
            results.add([
                "sourceId": modelUrn,
                "targetId": operationUrn,
                "externalId": "${modelUrn}->${operationUrn}".toString(),
                "typeName": "applies"
            ])
        }
    }
}

return results
