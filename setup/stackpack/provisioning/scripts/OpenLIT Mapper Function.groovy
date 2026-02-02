/**
 * OpenLIT Mapper Function
 * 
 * This function is used to infer GenAI architectural components (Systems, Models, Operations)
 * from OpenTelemetry topology elements or spans.
 */

def elementMap = element.asReadonlyMap()

// Robust extraction of attributes (Support spanAttributes for raw spans, or data.tags for topology elements)
def data = elementMap["data"]
def attributes = [:]
def resourceAttributes = [:]

if (elementMap["spanAttributes"]) {
    attributes = elementMap["spanAttributes"]
    resourceAttributes = elementMap["resourceAttributes"] ?: [:]
} else if (data instanceof String) {
    try {
        def parsedData = new groovy.json.JsonSlurper().parseText(data)
        attributes = parsedData["tags"] ?: [:]
        resourceAttributes = parsedData["tags"] ?: [:] // Resource attrs are often mixed in tags
    } catch (e) {
        // Not JSON
    }
} else if (data instanceof Map) {
    attributes = data["tags"] ?: [:]
    resourceAttributes = data["tags"] ?: [:]
}

// Check if this is a GenAI element
if (!attributes.containsKey("gen_ai.system")) {
    return null
}

def clusterName = resourceAttributes.get("k8s.cluster.name", "local")
def namespace = resourceAttributes.get("k8s.namespace.name", resourceAttributes.get("service.namespace", "default"))
def appName = attributes.get("gen_ai.application_name", resourceAttributes.get("service.name", "unknown-app"))
def systemName = attributes.get("gen_ai.system", "Unknown System")
def modelName = attributes.get("gen_ai.request.model")

// Common metadata
def commonData = [
    "integrationType": "openlit",
    "integrationUrl": clusterName,
    "cluster": clusterName,
    "namespace": namespace,
    "domain": "OpenLIT",
    "environments": ["default"]
]

// 1. Identify the Application URN (try to match OTel format)
def appUrn = elementMap["externalId"] ?: "urn:service:/${clusterName}:${namespace}:${appName}"

// 2. GenAI System Component
def systemUrn = "urn:genai:system:/${systemName.toLowerCase()}"
def systemType = "genai system ${systemName.toLowerCase()}"

// Verify if the system type exists, otherwise fallback to a generic one
def validSystems = ["ollama", "openai", "vllm"]
if (!validSystems.contains(systemName.toLowerCase())) {
    systemType = "genai system ollama" // Fallback to ollama which has a nice icon
}

context.component(systemUrn, systemType, [
    "name": systemName,
    "layer": "GenAiSystems",
    "genai_system": systemName
] + commonData)

// Relation: App -> uses -> System
context.relation(appUrn, systemUrn, "uses", [:])

if (modelName) {
    // 3. GenAI Model Component
    def modelUrn = "urn:genai:model:/${systemName.toLowerCase()}/${modelName.toLowerCase()}"
    context.component(modelUrn, "genai model", [
        "name": modelName,
        "layer": "Models",
        "genai_model": modelName,
        "genai_system": systemName
    ] + commonData)

    // Relation: System -> hosts -> Model
    context.relation(systemUrn, modelUrn, "hosts", [:])
    
    // Relation: App -> uses -> Model
    context.relation(appUrn, modelUrn, "uses", [:])
}

return null
