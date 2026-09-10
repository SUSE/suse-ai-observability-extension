// Specialize components emitted by the topology exporter when their discovery
// mechanism cannot express the final StackPack product type.

def data = element.data ?: [:]
def componentName = data.name?.toString()
def externalId = element.externalId?.toString()
def registryLegacyId = "urn:suse-ai:product:inference-engine:kubeflow-model-registry".toString()

if (componentName == "kubeflow-model-registry" || externalId == registryLegacyId) {
    def labels = []
    if (data.labels instanceof List) {
        data.labels.each { label ->
            if (label != null) {
                def value = label.toString()
                if (!value.startsWith("suse.ai.component.type:") &&
                    !value.startsWith("suse.ai.component.name:") &&
                    !value.startsWith("suse.ai.category:")) {
                    labels.add(value.toString())
                }
            }
        }
    }

    labels.add("suse.ai.component.type:ml-registry".toString())
    labels.add("suse.ai.component.name:kubeflow-model-registry".toString())
    labels.add("suse.ai.category:ml-registry".toString())
    data.labels = labels
    data.name = "kubeflow-model-registry".toString()
    data.layer = (data.layer ?: "Services").toString()
    data.domain = "genai".toString()
    element.type.name = "ml-registry.kubeflow".toString()
    element.data = data
}

element
