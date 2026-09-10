// Exercise the shipped scripts with the strict String/Set ID API shape.
import groovy.json.JsonOutput

def root = new File(args[0], 'stackpack/suse-ai/provisioning/templates/sync')
def canonical = 'urn:suse-ai:product:ml-registry:kubeflow-model-registry'
def legacy = 'urn:suse-ai:product:inference-engine:kubeflow-model-registry'
def mockSts = [createId: { String externalId, Set identifiers, String type ->
    assert identifiers.every { it instanceof String }
    [externalId: externalId, identifiers: identifiers, type: type]
}]
def evaluate = { String file, Map variables ->
    new GroovyShell(new Binding(variables)).evaluate(new File(root, file))
}

def product = evaluate('suse-ai-product-id-extractor.groovy', [Sts: mockSts, topologyElement: [
    externalId: 'urn:opentelemetry:service:model-registry-service',
    data: [tags: ['suse.ai.component.name': 'kubeflow-model-registry',
                  'suse.ai.component.type': 'ml-registry', 'k8s.namespace.name': 'ml-platform']],
]])
assert product.externalId == canonical
assert product.identifiers.contains(canonical)
assert !product.identifiers.contains('urn:opentelemetry:service:model-registry-service')
assert product.type == 'ml-registry.kubeflow'

[canonical, legacy].each { externalId ->
    def source = [externalId: externalId, typeName: 'inference-engine',
                  data: [name: 'kubeflow-model-registry', identifiers: [externalId]]]
    def extracted = evaluate('topology-sync-id-extractor.groovy', [Sts: mockSts,
        topologyElement: new Expando(asReadonlyMap: { -> source })])
    assert extracted.externalId == externalId // Relations still resolve the collector's ID.
    assert extracted.identifiers.contains(canonical)
    assert extracted.type == 'ml-registry.kubeflow'
}

[['k8s.namespace.name:ml-platform'], ['k8s.namespace.name:tenant-a', 'k8s.namespace.name:tenant-b'], []].each { namespaces ->
    def mapped = evaluate('topology-sync-component-mapping-function.groovy', [element: [
        externalId: legacy, type: [name: 'inference-engine'],
        data: [name: 'kubeflow-model-registry', labels: namespaces + [
            'k8s.cluster.name:alpha', 'suse.ai.component.type:inference-engine', null]],
    ]])
    assert mapped.externalId == legacy
    assert mapped.type.name == 'ml-registry.kubeflow'
    assert mapped.data.labels.findAll { it.startsWith('k8s.namespace.name:') } == namespaces
    assert mapped.data.labels.contains('k8s.cluster.name:alpha')
    assert mapped.data.labels.contains('suse.ai.component.type:ml-registry')
    assert !mapped.data.labels.contains('suse.ai.component.type:inference-engine')
}

def ordinary = [externalId: 'urn:suse-ai:product:vectordb:milvus', type: [name: 'vectordb'],
                data: [name: 'milvus', labels: ['k8s.namespace.name:tenant-a']]]
def before = JsonOutput.toJson(ordinary)
assert JsonOutput.toJson(evaluate('topology-sync-component-mapping-function.groovy', [element: ordinary])) == before
println 'PASS: metrics-only and legacy registry IDs, namespace preservation, unrelated products'
